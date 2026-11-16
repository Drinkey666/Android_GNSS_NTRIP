package com.example.ftpget

import android.location.GnssMeasurementsEvent
import android.os.SystemClock
import java.io.File
import java.io.RandomAccessFile
import java.util.Locale
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/** One serial queue owns JNI. The recorder's gateway orders receipts and GNSS callbacks.
 * Forecasts are frozen before init; reference coordinates are used only AFTER a solution.
 */
internal class LiveSsrSession(
    private val store:NtripCaptureStore, private val products:File,
    private val settings:NtripSettings, private val reference:ReferencePosition?,
    private val publish:(String,LivePppResult?)->Unit,
    private val fatal:(String)->Unit,
    private val prepareProducts:()->Unit = {},
) {
    private val worker=ThreadPoolExecutor(1,1,0,TimeUnit.SECONDS,ArrayBlockingQueue(512))
    private var initialized=false
    private var disabled=false
    private var appliedSeq=store.initialSequence
    private var lastEpochGps=Double.NEGATIVE_INFINITY
    private var nativeTouched=false
    private var attemptedAt=0L
    private var productsPrepared=false
    private val dir=store.directory
    private val epochs=File(dir,"epochs.csv").bufferedWriter()
    private val corrections=File(dir,"corrections.csv").bufferedWriter()
    private val observations=File(dir,"observations.csv").bufferedWriter()
    private val solutions=File(dir,"solutions.csv").bufferedWriter()
    private val errors=File(dir,"position_errors.csv").bufferedWriter()
    init {
        epochs.write("week,tow,callback_elapsed_ns,decision_elapsed_ns,applied_seq,status\n")
        corrections.write("callback_elapsed_ns,status\n")
        observations.write("week,tow,sat,signal,slot,P_m,L_cycle,D_Hz,CN0_dBHz,LLI,code\n")
        solutions.write("week,tow,Q,ns,nobs,x_m,y_m,z_m,lat_deg,lon_deg,h_m,std_x_m,std_y_m,std_z_m,processing_ms\n")
        errors.write(PositionErrorCsv.header)
    }
    private fun enqueue(work:()->Unit) {
        try {worker.execute {try {work()}catch(_:Exception){disabled=true;publish("LIVE_SESSION_ERROR：已停止解算，保留原始采集",null);fatal("LIVE_RECORD_ERROR")}}}
        catch(_:java.util.concurrent.RejectedExecutionException){fatal("LIVE_QUEUE_OVERFLOW")}
    }
    fun arrival(channel:Int,event:String,data:ByteArray,receipt:CaptureReceipt) = enqueue {
        if(initialized && !disabled) {
            if(event=="RESET")LivePppNative.nativeResetTransport(channel)
            if(event=="DATA" && !LivePppNative.nativeFeedRtcmAt(channel,data,receipt.utcNs)) {
                disabled=true;publish("WHU 解码停止：${LivePppNative.nativeLastError()}",null)
            }
        }
        appliedSeq=receipt.seq
    }
    /** Replay only receipts already ordered before this event. Never read future bytes. */
    private fun primeRecordedPrefix() {
        val raw=listOf("ssr.rtcm3","broadcast.rtcm3","bias.rtcm3").map { RandomAccessFile(File(dir,it),"r") }
        try {
            File(dir,"arrivals.csv").bufferedReader().use { reader ->
                reader.readLine()
                while(true) {
                    val line=reader.readLine() ?: error("SSR_PREFIX_TRUNCATED")
                    val c=line.split(',');val channel=c[3].toInt()
                    if(c[4]=="RESET")LivePppNative.nativeResetTransport(channel)
                    if(c[4]=="DATA") {
                        val b=ByteArray(c[6].toInt());raw[channel].seek(c[5].toLong());raw[channel].readFully(b)
                        check(LivePppNative.nativeFeedRtcmAt(channel,b,c[1].toLong())) { "SSR_PREFIX_DECODE_FAILED" }
                    }
                    if(c[0].toLong()==appliedSeq)break
                }
            }
        } finally {raw.forEach {it.close()}}
    }
    private fun snapshot(paths:Array<String>):Array<String> {
        val roles=listOf("ionex","vmf_first","vmf_second","orography","atx")
        val names=listOf("product_ionex.INX","product_vmf_first","product_vmf_second","product_orography","product_antenna.ATX")
        val result=paths.copyOf();val manifest=linkedMapOf<String,Any>()
        roles.forEachIndexed { i,role ->
            val source=File(paths[i+4]);val dest=File(dir,names[i]);val before=captureDigest(source)
            source.copyTo(dest,overwrite=true)
            check(captureDigest(dest)==before && captureDigest(source)==before) { "PRODUCT_CHANGED_DURING_COPY" }
            result[i+4]=dest.absolutePath
            manifest[role]=mapOf("name" to dest.name,"original_name" to source.name,"bytes" to dest.length(),"sha256" to before)
        }
        File(dir,"products.json").writeText(captureJson(mapOf("products" to manifest,
            "frozen_before_init_elapsed_ns" to SystemClock.elapsedRealtimeNanos()-store.startElapsed,
            "source" to "LOCAL_FORECAST_FILES","historical_publication_time_verified" to false,
            "note" to "Snapshot proves session contents, not original server publication time")))
        File(products,"forecast_download_receipt.json").takeIf {it.isFile}?.copyTo(File(dir,"forecast_download_receipt.json"),overwrite=true)
        return result
    }
    fun epoch(event:GnssMeasurementsEvent,callback:Long) = enqueue {
        val decision=SystemClock.elapsedRealtimeNanos()-store.startElapsed
        if(disabled)return@enqueue
        if(settings.correctionMount!="SSRC00WHU0" || settings.biasMount!="OSBC00WHU1" || !settings.centerOfMass) {
            store.productSetupFailed("SSR_PROFILE", "WHU SSRC00WHU0(CoM) + OSBC00WHU1 required")
            disabled=true;publish("仅采集：实时解算要求 WHU SSRC00WHU0(CoM) + OSBC00WHU1",null);return@enqueue
        }
        if(!initialized) {
            if(callback-attemptedAt<5_000_000_000L)return@enqueue
            attemptedAt=callback
            val paths=try {
                // Runs on the serial worker, before snapshot/JNI init. Upgrading
                // the APK must also migrate the known old local ANTEX when the
                // user starts SSR directly without opening the download page.
                if(!productsPrepared){prepareProducts();productsPrepared=true}
                LivePppProducts.resolveSsr(products,event.clock)
            }catch(e:Exception) {
                store.productSetupFailed("LOCAL_PRODUCTS", e.message)
                publish("PPP 未启用：${e.message}",null);return@enqueue
            }
            val frozen=snapshot(paths)
            nativeTouched=true
            initialized=LivePppNative.nativeInitSsr(frozen,File(dir,"live.trace").absolutePath,true)
            if(!initialized){
                val reason = LivePppNative.nativeLastError()
                store.productSetupFailed("NATIVE_INIT", reason)
                disabled=true;publish("PPP 未启用：$reason",null);return@enqueue
            }
            check(LivePppNative.nativeUseWhuProfile()) { "WHU_PROFILE_INIT_FAILED" }
            File(dir,"profile.txt").writeText(LivePppNative.nativeProfile()+"\nSOURCE=WHU_SSR_PLUS_FORECAST\nSSR_PROFILE=$WHU_SSR_PROFILE\n")
            primeRecordedPrefix()
            store.productInitialized()
        }
        val values=LivePppNative.nativeProcessEpoch(event.clock,event.measurements.toTypedArray())
        val stamp=LivePppNative.nativeEpochStamp()
        val status=if(values==null)LivePppNative.nativeLastError() else "Q_${values[2].toInt()}"
        // A cutoff is the last receipt actually applied by this worker, not phone UTC guessed as GNSS UTC.
        if(stamp!=null && stamp[0]*604800+stamp[1]>lastEpochGps) {
            epochs.write(String.format(Locale.US,"%d,%.9f,%d,%d,%d,%s\n",stamp[0].toInt(),stamp[1],callback-store.startElapsed,decision,appliedSeq,status.replace(',',';').replace('\n',' ')))
            lastEpochGps=stamp[0]*604800+stamp[1]
        }
        epochs.flush()
        corrections.write("${callback-store.startElapsed},${LivePppNative.nativeCorrectionStatus().replace(',',';')}\n");corrections.flush()
        observations.write(LivePppNative.nativeObsRows());observations.flush()
        if(values==null){store.recordPppResult(null,status,callback);publish(status,null);return@enqueue}
        val r=LivePppResult.fromNative(values)
        solutions.write(String.format(Locale.US,"%d,%.9f,%d,%d,%d,%.9f,%.9f,%.9f,%.12f,%.12f,%.6f,%.6f,%.6f,%.6f,%.3f\n",
            r.week,r.tow,r.q,r.satellites,r.observedSatellites,r.x,r.y,r.z,r.latitude,r.longitude,r.height,r.stdX,r.stdY,r.stdZ,r.processingMs))
        solutions.flush();errors.write(PositionErrorCsv.row(reference,SolutionCoordinate.fromLive(r),"LIVE"));errors.flush()
        store.recordPppResult(r,status,callback)
        publish(if(r.q==6)"PPP 浮点解；精度尚待 PC 验证" else "当前 Q=${r.q}，不代表 PPP 成功",r)
    }
    /** Called only after both the socket workers and Raw callback producer stop. */
    fun close() {
        worker.shutdown();check(worker.awaitTermination(30,TimeUnit.SECONDS)) { "LIVE_WORKER_NOT_DRAINED" }
        if(nativeTouched)LivePppNative.nativeRelease()
        listOf(epochs,corrections,observations,solutions,errors).forEach {it.close()}
    }
}
