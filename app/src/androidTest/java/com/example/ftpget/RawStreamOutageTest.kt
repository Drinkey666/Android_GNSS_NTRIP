package com.example.ftpget

import android.content.Context
import android.content.Intent
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import java.util.zip.ZipFile

/** Requires a device delivering real raw GNSS measurements. Only the caster is simulated. */
@RunWith(AndroidJUnit4::class)
class RawStreamOutageTest {
    private fun await(label: String, seconds: Int, condition: () -> Boolean) {
        val end = SystemClock.elapsedRealtime() + 1000L * seconds
        while (!condition()) {
            if (SystemClock.elapsedRealtime() >= end) fail("Timed out: $label")
            Thread.sleep(100)
        }
    }

    private class Caster : AutoCloseable {
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        private val clients = Executors.newCachedThreadPool()
        @Volatile var outage = false
        @Volatile private var navRejected = false
        // CRC-valid private message, deliberately supplies no positioning product.
        private val frame = byteArrayOf(0xD3.toByte(),0,2,0xFF.toByte(),0xA0.toByte()).let {
            val crc = RtcmCaptureScanner.crc24(it)
            it + byteArrayOf((crc shr 16).toByte(),(crc shr 8).toByte(),crc.toByte())
        }
        init {
            clients.execute {
                while (!server.isClosed) {
                    val socket = try { server.accept() } catch (_: java.io.IOException) { break }
                    clients.execute { socket.use { runCatching { respond(it) } } }
                }
            }
        }
        private fun respond(socket: Socket) {
            socket.soTimeout = 3000
            val reader = socket.getInputStream().bufferedReader()
            val mount = reader.readLine().substringAfter("GET /").substringBefore(' ')
            while (!reader.readLine().isNullOrEmpty()) { }
            val out = socket.getOutputStream()
            if (mount == "BCEP00BKG0" && (outage || navRejected)) {
                navRejected = true
                out.write("HTTP/1.1 404 Not Found\r\n\r\n".toByteArray())
            } else if (outage) {
                out.write("HTTP/1.1 503 Unavailable\r\n\r\n".toByteArray())
            } else {
                out.write("HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\n\r\n".toByteArray())
                while (!outage && !server.isClosed) {
                    out.write(frame)
                    out.flush()
                    Thread.sleep(200)
                }
            }
        }
        override fun close() {
            server.close()
            clients.shutdownNow()
        }
    }

    @Test fun rawContinuesDuringTotalOutageAndAfterOneMountStops() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        val root = requireNotNull(app.getExternalFilesDir("GNSS_NTRIP"))
        val prefs = app.getSharedPreferences("ntrip_capture", Context.MODE_PRIVATE)
        val previousArchive = prefs.getString("archive", null)
        check(!CaptureSession.display.value.active && CaptureSession.pending == null)
        val previousDirs = root.listFiles().orEmpty().map { it.name }.toSet()
        val service = Intent(app, NtripCaptureService::class.java)
        Caster().use { caster ->
            val settings = NtripSettings(host="127.0.0.1", port=caster.server.localPort,
                correctionMount="SSRC00WHU0", centerOfMass=true, biasMount="OSBC00WHU1")
            CaptureSession.pending = CaptureStart(settings,NtripCredentials("",""),null,3)
            app.startForegroundService(service)
            var dir: File? = null
            try {
                await("new capture and three connected streams", 20) {
                    dir = root.listFiles().orEmpty().singleOrNull {
                        it.isDirectory && it.name.startsWith("Capture_") && it.name !in previousDirs
                    }
                    val d = CaptureSession.display.value
                    dir != null && d.active && minOf(d.ssrFrames,d.navFrames,d.biasFrames) > 0
                }
                val capture = requireNotNull(dir)
                val anchors = File(capture,"clock_anchors.csv")
                fun anchorsReceived() = anchors.useLines { it.drop(1).count() }
                // A cold receiver can deliver several clock-only callbacks. Wait
                // for measurements visible in the real writer before cutting the streams.
                await("four recorded Raw epochs before outage",60) {
                    val txt = capture.listFiles().orEmpty().singleOrNull { it.name.startsWith("RawData_") }
                    txt?.useLines { lines ->
                        lines.filter { it.startsWith("Raw,") }.mapNotNull { it.split(',').getOrNull(2)?.toLongOrNull() }
                            .distinct().take(4).count() == 4
                    } == true
                }
                caster.outage = true
                await("all three streams closed",10) {
                    val closed = File(capture,"arrivals.csv").readLines().filter { ",CLOSED," in it }
                    closed.map { it.split(',')[3] }.toSet().size == 3
                }
                val outageStart = SystemClock.elapsedRealtimeNanos()
                val startCount = anchorsReceived()
                await("terminal 404 and GNSS callbacks with all streams down",25) {
                    CaptureSession.display.value.nav == "NTRIP_HTTP_404" && anchorsReceived() >= startCount+4
                }
                assertTrue(CaptureSession.display.value.active && !CaptureSession.display.value.stopping)
                val outageEnd = SystemClock.elapsedRealtimeNanos()
                val display = CaptureSession.display.value
                caster.outage = false
                await("two streams resumed",25) {
                    val d = CaptureSession.display.value
                    d.ssrFrames > display.ssrFrames && d.biasFrames > display.biasFrames
                }
                val restored = SystemClock.elapsedRealtimeNanos()
                val beforeTail = anchorsReceived()
                await("GNSS callbacks after reconnect",10) { anchorsReceived() >= beforeTail+4 }
                app.startService(Intent(service).setAction(NtripCaptureService.STOP))
                await("complete archive",30) { !CaptureSession.display.value.active && File(root,capture.name+".zip").isFile }
                ZipFile(File(root,capture.name+".zip")).use { zip ->
                    fun contents(name:String) = zip.getInputStream(zip.getEntry(name)).bufferedReader().use { it.readLines() }
                    val m = JSONObject(contents("capture.json").joinToString(""))
                    assertEquals("USER_STOP",m.getString("stop_reason"))
                    assertTrue(m.getBoolean("complete"))
                    val raw = m.getJSONObject("observation")
                    assertEquals(0L,raw.getLong("dropped_measurements"))
                    assertTrue(raw.isNull("write_error"))
                    val rawRows = contents(raw.getString("name")).filter { it.startsWith("Raw,") }
                    val times = rawRows.map { it.split(',')[2] }.toSet()
                    val callbacks = contents("clock_anchors.csv").drop(1).map { it.split(',') }
                        .filter { it[0] in times }.map { it[7].toLong() }
                    val recordings = listOf(callbacks.count { it < outageStart },
                        callbacks.count { it in outageStart until outageEnd },callbacks.count { it >= restored })
                    assertTrue("Raw epochs before/during/after: $recordings",recordings.all { it >= 2 })
                    val zero = m.getLong("start_elapsed_realtime_ns")
                    assertFalse(contents("arrivals.csv").drop(1).any {
                        val r = it.split(',')
                        r[4]=="DATA" && zero+r[2].toLong() in outageStart until outageEnd
                    })
                    android.util.Log.i("RawOutageTest","archive=${capture.name} raw_rows=${rawRows.size} " +
                        "raw_epochs_before_during_after=$recordings outage_s=${(outageEnd-outageStart)/1e9}")
                }
            } finally {
                if (CaptureSession.display.value.active) {
                    app.startService(Intent(service).setAction(NtripCaptureService.STOP))
                    await("test capture stopped",30) { !CaptureSession.display.value.active }
                }
                val testArchive = dir?.let { File(root,it.name+".zip").absolutePath }
                if (testArchive != null && prefs.getString("archive",null)==testArchive)
                    prefs.edit().putString("archive",previousArchive).commit()
            }
        }
    }
}
