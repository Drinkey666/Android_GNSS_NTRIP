package com.example.ftpget

import java.io.File
import java.io.BufferedWriter
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.math.abs

/** Platform-independent, deterministic capture format shared with PPP_NTRIP_PC. */
internal class RtcmCaptureScanner {
    private var pending = ByteArray(0)
    var frames = 0L; private set
    var crcFailures = 0L; private set
    val types = sortedMapOf<Int, Long>()
    val subtypes = sortedMapOf<Int, Long>()
    fun reset() { pending = ByteArray(0) }
    fun feed(data: ByteArray) {
        pending += data
        var at = 0
        while (pending.size - at >= 3) {
            if (pending[at].toInt() and 255 != 0xD3 || pending[at+1].toInt() and 0xFC != 0) { at++; continue }
            val length = ((pending[at+1].toInt() and 3) shl 8) + (pending[at+2].toInt() and 255) + 6
            if (pending.size - at < length) break
            val end = at + length - 3
            val expected = ((pending[end].toInt() and 255) shl 16) or
                ((pending[end+1].toInt() and 255) shl 8) or (pending[end+2].toInt() and 255)
            if (crc24(pending, at, length-3) != expected) { crcFailures++; at++; continue }
            if (length >= 8) {
                val type = ((pending[at+3].toInt() and 255) shl 4) or ((pending[at+4].toInt() and 255) ushr 4)
                types[type] = (types[type] ?: 0) + 1
                if (type == 4076 && length >= 9) {
                    val subtype = ((pending[at+4].toInt() and 1) shl 7) or ((pending[at+5].toInt() and 255) ushr 1)
                    subtypes[subtype] = (subtypes[subtype] ?: 0) + 1
                }
            }
            frames++; at += length
        }
        pending = pending.copyOfRange(at, pending.size)
    }
    companion object {
        fun crc24(b: ByteArray, start: Int = 0, size: Int = b.size): Int {
            var crc = 0
            for (i in start until start + size) {
                crc = crc xor ((b[i].toInt() and 255) shl 16)
                repeat(8) { crc = crc shl 1; if (crc and 0x1000000 != 0) crc = crc xor 0x1864CFB }
            }
            return crc and 0xFFFFFF
        }
    }
}

internal fun captureJson(value: Any?): String = when (value) {
    null -> "null"
    is String -> buildString {
        append('"'); value.forEach { c -> when(c) {
            '"' -> append("\\\""); '\\' -> append("\\\\"); '\n' -> append("\\n"); '\r' -> append("\\r"); '\t' -> append("\\t")
            else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
        } }; append('"')
    }
    is Boolean, is Long, is Int -> value.toString()
    is Double -> { require(value.isFinite()); value.toString() }
    is Map<*, *> -> value.entries.joinToString(prefix="{",postfix="}") { captureJson(it.key.toString())+":"+captureJson(it.value) }
    is Iterable<*> -> value.joinToString(prefix="[",postfix="]") { captureJson(it) }
    else -> error("CAPTURE_JSON_TYPE_INVALID")
}

internal fun captureDigest(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input -> val b=ByteArray(32768); while(true) { val n=input.read(b); if(n<0)break;digest.update(b,0,n) } }
    return digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
}

/** UTC anchor plus elapsedRealtime; receipts identify exactly what the serial solver applied. */
internal data class CaptureReceipt(val seq:Long,val utcNs:Long,val elapsedNs:Long)

internal class NtripCaptureStore(
    val directory: File, private val settings: NtripSettings,
    private val utcNanos: () -> Long, private val elapsedNanos: () -> Long,
    private val maxBytes: Long = 128L * 1024 * 1024,
) {
    val startUtc = utcNanos()
    val startElapsed = elapsedNanos()
    private val rawNames = listOf("ssr.rtcm3", "broadcast.rtcm3") + if(settings.biasMount.isEmpty()) emptyList() else listOf("bias.rtcm3")
    private val format = if(settings.biasMount.isEmpty()) "PPP_NTRIP_CAPTURE_V1" else "PPP_NTRIP_CAPTURE_V2"
    val initialSequence:Long get()=rawNames.size.toLong()-1
    private val raw: List<java.io.OutputStream>
    private val timeline: BufferedWriter
    private val anchors: BufferedWriter
    private val offset = LongArray(rawNames.size)
    private var seq = 0L
    private var lastUtc = startUtc
    private var closed = false
    private var clockStep = false
    var anchorCount = 0L; private set
    val scanner = rawNames.map { RtcmCaptureScanner() }
    private val httpOk = BooleanArray(rawNames.size)
    private val failures = mutableListOf<Map<String,Any>>()
    val bytes: Long @Synchronized get() = offset.sum()
    @Synchronized fun counts() = Triple(offset.sum(),scanner[0].frames,scanner[1].frames)
    @Synchronized fun biasFrames() = scanner.getOrNull(2)?.frames ?: 0L
    init {
        settings.validate()
        require(!directory.exists() && directory.mkdirs()) { "CAPTURE_DIRECTORY_EXISTS_OR_UNWRITABLE" }
        raw = rawNames.map { File(directory,it).outputStream().buffered() }
        timeline = File(directory,"arrivals.csv").bufferedWriter(Charsets.US_ASCII)
        timeline.write("seq,utc_ns,elapsed_ns,channel,event,offset,length,reason\n")
        anchors = File(directory,"clock_anchors.csv").bufferedWriter(Charsets.US_ASCII)
        anchors.write("time_nanos,full_bias_nanos,bias_nanos,hcdc,leap_second,gnss_elapsed_realtime_ns,elapsed_uncertainty_ns,callback_elapsed_realtime_ns\n")
        File(directory,"capture.json").writeText(captureJson(mapOf("format" to format,"complete" to false)),Charsets.UTF_8)
        rawNames.indices.forEach { event(it,"START") }
    }
    @Synchronized fun event(channel: Int, event: String, data: ByteArray = byteArrayOf(), reason: String = ""): CaptureReceipt {
        check(!closed); require(channel in rawNames.indices && data.size <= 16384)
        require(event in listOf("START","END","RESET","CONNECTED","DATA","CLOSED"))
        require(reason.matches(Regex("[A-Za-z0-9_]*")))
        val elapsed = elapsedNanos() - startElapsed
        val utc = startUtc + elapsed
        if (abs(utcNanos()-utc)>500_000_000L) { clockStep=true;error("PC_CLOCK_STEP_STOP_RECORDING") }
        check(offset.sum()+data.size<=maxBytes) { "SIZE_LIMIT_REACHED" }
        require((event=="DATA") == data.isNotEmpty())
        if (event=="RESET") scanner[channel].reset()
        if (event=="CONNECTED") httpOk[channel]=true
        if (event=="CLOSED" && reason.isNotEmpty()) failures += mapOf("channel" to channel,"reason" to reason)
        val begin=offset[channel]
        if(data.isNotEmpty()) { raw[channel].write(data);raw[channel].flush();offset[channel]+=data.size;scanner[channel].feed(data) }
        val receipt=CaptureReceipt(seq++,utc,elapsed)
        timeline.write("${receipt.seq},$utc,$elapsed,$channel,$event,$begin,${data.size},$reason\n");timeline.flush();lastUtc=utc
        return receipt
    }
    @Synchronized fun clockAnchor(fields: List<String>) {
        check(!closed); require(fields.size==8 && fields.none { it.contains(',') || it.contains('\n') || it.contains('\r') })
        anchors.write(fields.joinToString(",")+"\n");anchors.flush();anchorCount++
    }
    @Synchronized fun finish(txt: File?, dropped: Long, txtError: String?, stopReason: String): File {
        check(!closed)
        var ended=true
        try {if(!clockStep) { rawNames.indices.forEach { event(it,"END") } }}catch(_:Exception){ended=false}
        (raw + listOf(timeline,anchors)).forEach { stream ->
            if(runCatching { stream.close() }.isFailure)ended=false
        }
        closed=true
        fun info(file: File) = mapOf("bytes" to file.length(),"sha256" to captureDigest(file))
        val config=mutableMapOf("host" to settings.host,"port" to settings.port,"tls" to settings.tls,
            "ssr_mount" to settings.correctionMount,"broadcast_mount" to settings.navigationMount,
            "bias_mount" to settings.biasMount,
            "orbit_reference" to if(settings.centerOfMass)"COM" else "APC",
            "reference_pairs" to mapOf("GPS" to listOf("1W","2W"),"GAL" to listOf("1C","5Q"),"BDS" to listOf("2I","6I")))
        if(settings.biasMount.isEmpty())config.remove("bias_mount")
        if(settings.correctionMount=="SSRC00WHU0" && settings.biasMount=="OSBC00WHU1" && settings.centerOfMass)
            config["ssr_profile"]="WHU_OSB_CONTINUITY_V1"
        if(clockStep)failures+=mapOf("channel" to 0,"reason" to "PC_CLOCK_STEP_STOP_RECORDING")
        val manifest=mapOf("format" to format,"complete" to (!clockStep && ended),"platform" to "ANDROID",
            "config" to config,"pc_clock_sync_verified" to false,"clock" to "PHONE_UTC_ANCHOR_PLUS_ELAPSED_REALTIME_NS",
            "start_utc_ns" to startUtc,"start_elapsed_realtime_ns" to startElapsed,"end_utc_ns" to lastUtc,"end_elapsed_ns" to (lastUtc-startUtc),"max_mib" to maxBytes/1048576,"duration_limit_seconds" to 1800,
            "total_bytes" to offset.sum(),"credential_storage" to "NONE","ppp_ready" to false,"failures" to failures,
            "stop_reason" to stopReason,"transport_received_both" to scanner.all { it.frames>0 },
            "files" to (rawNames+"arrivals.csv").associateWith { info(File(directory,it)) },
            "attachments" to directory.listFiles()!!.filter { it.isFile && it.name !in rawNames+listOf("arrivals.csv","capture.json",txt?.name,"clock_anchors.csv") && !it.name.endsWith(".part") }.associate { it.name to info(it) },
            "streams" to scanner.mapIndexed { i,s -> mapOf("mount" to listOf(settings.correctionMount,settings.navigationMount,settings.biasMount)[i],
                "http_status" to if(httpOk[i])200 else null,"bytes" to offset[i],"valid_rtcm_frames" to s.frames,
                "crc_failures" to s.crcFailures,"message_types" to s.types,"igs_subtypes" to s.subtypes) },
            "observation" to txt?.let { mapOf("name" to it.name,"bytes" to it.length(),"sha256" to captureDigest(it),
                "dropped_measurements" to dropped,"write_error" to txtError) },
            "clock_anchors" to (info(File(directory,"clock_anchors.csv"))+mapOf("name" to "clock_anchors.csv","count" to anchorCount)))
        val manifestFile=File(directory,"capture.json")
        val temporary=File(directory,"capture.json.part");temporary.writeText(captureJson(manifest),Charsets.UTF_8)
        check(manifestFile.delete() && temporary.renameTo(manifestFile)) { "MANIFEST_FINALIZE_FAILED" }
        return archive()
    }
    private fun archive(): File {
        val target=File(directory.parentFile,directory.name+".zip")
        check(!target.exists())
        val temporary=File(directory.parentFile,directory.name+".zip.part")
        ZipOutputStream(temporary.outputStream().buffered()).use { zip ->
            directory.listFiles()!!.filter { it.isFile && !it.name.endsWith(".part") }.sortedBy { it.name }.forEach { file ->
                zip.putNextEntry(ZipEntry(file.name));file.inputStream().use { it.copyTo(zip) };zip.closeEntry()
            }
        }
        check(temporary.renameTo(target)) { "ARCHIVE_FINALIZE_FAILED" };return target
    }
}
