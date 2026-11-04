package com.example.ftpget

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.GnssClock
import android.os.*
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.atomic.AtomicBoolean

data class CaptureDisplay(val active: Boolean=false,val stopping: Boolean=false,
    val ssr: String="",val nav: String="",val bytes: Long=0,val ssrFrames:Long=0,val navFrames:Long=0,
    val message: String="",val archive: String?=null,
    val pppStatus:String="等待 WHU 产品检查，尚未启用 PPP",val solution:LivePppResult?=null,
    val bias:String="",val biasFrames:Long=0)
internal data class CaptureStart(val settings:NtripSettings,val credentials:NtripCredentials,val reference:ReferencePosition?=null)
internal object CaptureSession {
    val display=MutableStateFlow(CaptureDisplay())
    @Volatile var pending:CaptureStart?=null
}

/** Foreground acquisition and optional WHU-only PPP, driven by the SAME Raw event. */
class NtripCaptureService:Service() {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private val stopping=AtomicBoolean(false)
    private val clients=mutableListOf<NtripClient>()
    private var store:NtripCaptureStore?=null
    private var logger:GnssDataLogger?=null
    private var live:LiveSsrSession?=null
    private val gateway=Any()
    private var wake:PowerManager.WakeLock?=null
    private var started=false
    private val main=Handler(Looper.getMainLooper())
    override fun onBind(intent:Intent?)=null
    private fun publish(change:(CaptureDisplay)->CaptureDisplay) { synchronized(CaptureSession) { CaptureSession.display.value=change(CaptureSession.display.value) } }
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action==STOP) { finish("USER_STOP");return START_NOT_STICKY }
        if(started)return START_NOT_STICKY
        val request=CaptureSession.pending;CaptureSession.pending=null
        if(request==null){stopSelf();return START_NOT_STICKY}
        started=true
        try {
            check(ContextCompat.checkSelfPermission(this,Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED)
            val manager=getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(CHANNEL,getString(R.string.capture_channel),NotificationManager.IMPORTANCE_LOW))
            val stop=PendingIntent.getService(this,0,Intent(this,NtripCaptureService::class.java).setAction(STOP),PendingIntent.FLAG_IMMUTABLE)
            val open=PendingIntent.getActivity(this,1,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE)
            val notification=NotificationCompat.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_gps_fixed_24)
                .setContentTitle(getString(R.string.capture_notification_title)).setContentText(getString(R.string.capture_notification_text))
                .setOngoing(true).setContentIntent(open).addAction(0,getString(R.string.capture_stop),stop).build()
            if(Build.VERSION.SDK_INT>=29)startForeground(27,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            else startForeground(27,notification)
            wake=(getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"PPP_NTRIP:recording")
                .apply { acquire(31*60*1000L) }
            val root=getExternalFilesDir("GNSS_NTRIP") ?: File(filesDir,"GNSS_NTRIP")
            check(root.isDirectory || root.mkdirs())
            val name="Capture_"+SimpleDateFormat("yyyyMMdd_HHmmss",Locale.US).format(Date())+"_"+UUID.randomUUID().toString().take(8)
            val recording=NtripCaptureStore(File(root,name),request.settings,{System.currentTimeMillis()*1000000L},SystemClock::elapsedRealtimeNanos)
            store=recording
            File(recording.directory,"software.json").writeText(captureJson(mapOf(
                "package" to packageName,"version_name" to BuildConfig.VERSION_NAME,
                "version_code" to BuildConfig.VERSION_CODE,
                "apk_sha256" to captureDigest(File(applicationInfo.sourceDir)),
                "manufacturer" to Build.MANUFACTURER,"model" to Build.MODEL,
                "sdk" to Build.VERSION.SDK_INT,"raw_schema" to "PROJECT_RAW_54_V1")))
            if(request.settings.biasMount.isNotEmpty()) {
                val productDirectory=getExternalFilesDir("GNSS_Products")?:File(filesDir,"GNSS_Products")
                live=LiveSsrSession(recording,productDirectory,request.settings,request.reference,
                    publish={status,result -> publish {it.copy(pppStatus=status,solution=result)}},fatal=::finish,
                    prepareProducts={BundledProducts.ensure(applicationContext,productDirectory) { message ->
                        publish {it.copy(pppStatus=message)}
                    }})
            }
            logger=GnssDataLogger(this,recording.directory,
                clockObserver={clock,callback ->
                    try {recording.clockAnchor(anchor(clock,callback))}
                    catch(_:Exception){finish("CLOCK_ANCHOR_WRITE_FAILED")}},
                eventObserver={event,callback -> synchronized(gateway) {live?.epoch(event,callback)}})

            check(logger!!.startRecording()) { "RAW_REGISTRATION_FAILED" }
            publish { CaptureDisplay(active=true,message=getString(R.string.capture_active)) }
            (listOf(request.settings.correctionMount,request.settings.navigationMount)+listOf(request.settings.biasMount).filter {it.isNotEmpty()}).forEachIndexed { channel,mount ->
                val client=NtripClient(request.settings,mount,request.credentials,
                    onConnect={if(!stopping.get())try { synchronized(gateway) {
                        if(!stopping.get())for(event in listOf("RESET","CONNECTED")) {
                            val receipt=recording.event(channel,event)
                            live?.arrival(channel,event,byteArrayOf(),receipt)
                        }
                    } }
                        catch(_:Exception){finish("SSR_WRITE_OR_LIMIT_FAILED")}},
                    onBytes={bytes -> if(!stopping.get())try {synchronized(gateway) {
                        if(!stopping.get()) {val receipt=recording.event(channel,"DATA",bytes);live?.arrival(channel,"DATA",bytes,receipt)}
                    }}
                        catch(_:Exception){finish("SSR_WRITE_OR_LIMIT_FAILED")}},
                    onStatus={status ->
                        publish { if(channel==0)it.copy(ssr=status) else if(channel==1)it.copy(nav=status) else it.copy(bias=status) }
                        if(status!="CONNECTING" && status!="CONNECTED_WAITING_RTCM" && !stopping.get()) {
                            runCatching {synchronized(gateway) {if(!stopping.get()) {
                                val receipt=recording.event(channel,"CLOSED",reason=status)
                                live?.arrival(channel,"CLOSED",byteArrayOf(),receipt)
                            }}}
                        }
                        if(status.startsWith("NTRIP_HTTP_4") || status=="NTRIP_SOURCETABLE_NOT_CORRECTION")finish(status)
                    })
                synchronized(clients) { if(!stopping.get()){clients+=client;client.start()} }
            }
            scope.launch {
                val start=SystemClock.elapsedRealtime()
                while(!stopping.get()) {
                    delay(1000);val counts=recording.counts()
                    publish {it.copy(bytes=counts.first,ssrFrames=counts.second,navFrames=counts.third,biasFrames=recording.biasFrames())}
                    if(SystemClock.elapsedRealtime()-start>=1800000L)finish("DURATION_LIMIT")
                    if((logger?.currentSaveFile?.length()?:0)>256L*1024*1024)finish("TXT_SIZE_LIMIT")
                    if(logger?.recordingErrorClass!=null)finish("TXT_WRITE_FAILED")
                }
            }
        }catch(_:Exception){finish("CAPTURE_START_FAILED")}
        return START_NOT_STICKY
    }
    private fun anchor(c:GnssClock,callback:Long):List<String> = listOf(
        c.timeNanos.toString(),if(c.hasFullBiasNanos())c.fullBiasNanos.toString() else "",
        if(c.hasBiasNanos())c.biasNanos.toString() else "",c.hardwareClockDiscontinuityCount.toString(),
        if(c.hasLeapSecond())c.leapSecond.toString() else "",
        if(Build.VERSION.SDK_INT>=29 && c.hasElapsedRealtimeNanos())c.elapsedRealtimeNanos.toString() else "",
        if(Build.VERSION.SDK_INT>=29 && c.hasElapsedRealtimeUncertaintyNanos())c.elapsedRealtimeUncertaintyNanos.toString() else "",callback.toString())
    private fun finish(reason:String) {
        if(!stopping.compareAndSet(false,true))return
        publish {it.copy(active=true,stopping=true,message=getString(R.string.capture_finishing))}
        scope.launch {
            var archive:File?=null
            var message=getString(R.string.capture_saved)
            try {
                val owned=synchronized(clients){clients.toList()}
                owned.forEach {it.stop()}
                // Finish every admitted Raw event (including clock anchor and ledger post)
                // before closing JNI. Do not gate its observers on the earlier stop request.
                val txt=logger?.stopRecording()
                check(owned.all {it.awaitStopped()}) {"NTRIP_WORKER_NOT_STOPPED"}
                live?.close();live=null
                archive=store?.finish(txt,logger?.droppedMeasurementCount?:0,logger?.recordingErrorClass,reason)
                if(archive==null)message=getString(R.string.capture_failed,reason)
                else {
                    getSharedPreferences("ntrip_capture",MODE_PRIVATE).edit().putString("archive",archive.absolutePath).apply()
                    if(reason!="USER_STOP" && reason!="DURATION_LIMIT")message=getString(R.string.capture_saved_with_warning,reason)
                    if((logger?.droppedMeasurementCount?:0)>0 || logger?.recordingErrorClass!=null)message=getString(R.string.capture_saved_with_warning,"TXT_INCOMPLETE")
                }
            } catch(_:Exception) {message=getString(R.string.capture_failed,reason)}
            finally {
                // Startup failure still unregisters GNSS / drains any opened TXT channel.
                runCatching {logger?.stopRecording()}
                runCatching {live?.close()};live=null
                if(wake?.isHeld==true)wake?.release()
                publish {it.copy(active=false,stopping=false,message=message,archive=archive?.absolutePath)}
                withContext(Dispatchers.Main){stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()}
                scope.cancel()
            }
        }
    }
    override fun onDestroy(){if(started && !stopping.get())finish("SERVICE_DESTROYED");super.onDestroy()}
    override fun onTimeout(startId:Int,fgsType:Int){finish("SERVICE_TIMEOUT");stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()}
    companion object {const val STOP="com.example.pppntrip.STOP_CAPTURE";private const val CHANNEL="ntrip_capture"}
}
