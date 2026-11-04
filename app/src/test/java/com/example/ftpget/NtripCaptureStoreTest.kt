package com.example.ftpget

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.util.zip.ZipFile

class NtripCaptureStoreTest {
    private fun packet(type:Int):ByteArray {
        val body=byteArrayOf((type ushr 4).toByte(),(type shl 4).toByte(),0,1)
        val b=byteArrayOf(0xD3.toByte(),0,4)+body
        val crc=RtcmCaptureScanner.crc24(b)
        return b+byteArrayOf((crc ushr 16).toByte(),(crc ushr 8).toByte(),crc.toByte())
    }
    private fun directory(label:String):File {
        val parent=File("build/ntrip_capture_fixtures");parent.mkdirs()
        return File(parent,label+"_"+System.nanoTime())
    }
    @Test fun scannerPreservesSplitFramesAndResynchronizes() {
        val s=RtcmCaptureScanner();val p=packet(1060)
        s.feed(p.copyOfRange(0,4));assertEquals(0L,s.frames)
        s.feed(p.copyOfRange(4,p.size));assertEquals(1L,s.frames)
        val bad=p.copyOf();bad[bad.lastIndex]=(bad.last().toInt() xor 1).toByte()
        s.feed(bad+p);assertEquals(2L,s.frames);assertEquals(1L,s.crcFailures)
        s.feed(p.copyOfRange(0,4));s.reset();s.feed(p.copyOfRange(4,p.size));assertEquals(2L,s.frames)
    }
    @Test fun pairedArchiveIsCompatibleAndContainsNoCredentials() {
        val dir=directory("paired")
        val utc=1700000000000000000L;var elapsed=1000000000L
        val store=NtripCaptureStore(dir,NtripSettings(),{utc+elapsed-1000000000L},{elapsed})
        elapsed+=100000000L;store.event(0,"RESET");store.event(0,"CONNECTED");store.event(0,"DATA",packet(1060))
        store.event(1,"RESET");store.event(1,"CONNECTED");store.event(1,"DATA",packet(1019))
        val txt=File(dir,"RawData_20231114_221320.txt")
        val gpsAtStart=utc-315964800000000000L+18000000000L
        txt.bufferedWriter().use { w ->
            w.write("# transport fixture; not real GNSS or accuracy evidence\n")
            for(i in 1..3) {
                val gps=gpsAtStart+i*1000000000L
                val row=MutableList(54){""};row[0]="Raw";row[1]=((utc+i*1000000000L)/1000000L).toString()
                row[2]=(1000000000L+i*1000000000L).toString();row[5]=(1000000000L-gpsAtStart).toString();row[6]="0";row[10]="0"
                row[11]="1";row[12]="0";row[13]="9";row[14]=(gps%604800000000000L-75000000L).toString()
                row[15]="10";row[16]="40";row[17]="0";row[18]=".1";row[19]="1";row[20]="22000000";row[21]=".1"
                row[22]="1575420000";row[28]="1";row[35]="C";row[36]=(1000000000L+i*1000000000L).toString()
                w.write(row.joinToString(",")+"\n")
            }
        }
        elapsed=5000000000L
        store.clockAnchor(listOf("3000000000",(1000000000L-gpsAtStart).toString(),"0","0","18","3000000000","1000","3000000100"))
        val zip=store.finish(txt,0,null,"USER_STOP")
        assertTrue(zip.isFile)
        ZipFile(zip).use { z ->
            for(name in listOf("capture.json","arrivals.csv","ssr.rtcm3","broadcast.rtcm3","clock_anchors.csv",txt.name)) {
                val entry=z.getEntry(name);assertNotNull(entry)
                assertArrayEquals(File(dir,name).readBytes(),z.getInputStream(entry).readBytes())
            }
            val manifest=z.getInputStream(z.getEntry("capture.json")).bufferedReader().readText()
            assertTrue(manifest.contains("\"complete\":true"));assertTrue(manifest.contains("\"transport_received_both\":true"))
            assertFalse(manifest.contains("Authorization"));assertFalse(manifest.contains("password"));assertFalse(manifest.contains("username"))
        }
        // A stable fixture location for the PC cross-language importer test.
        zip.copyTo(File(zip.parentFile,"pc_compatible_fixture.zip"),overwrite=true)
    }
    @Test fun clockStepNeverProducesCompleteCapture() {
        val dir=directory("clock_step");var wall=1700000000000000000L
        val store=NtripCaptureStore(dir,NtripSettings(),{wall},{1000000000L})
        wall+=2000000000L
        assertTrue(runCatching {store.event(0,"DATA",packet(1060))}.isFailure)
        store.finish(null,0,null,"CLOCK_STEP")
        assertTrue(File(dir,"capture.json").readText().contains("\"complete\":false"))
    }
    @Test fun limitsDoNotWriteOversizedChunkOrOverwriteDirectory() {
        val dir=directory("limits");val store=NtripCaptureStore(dir,NtripSettings(),{1700000000000000000L},{0L},maxBytes=5)
        assertTrue(runCatching {store.event(0,"DATA",packet(1060))}.isFailure)
        assertEquals(0L,store.bytes)
        store.finish(null,0,null,"SIZE_LIMIT")
        assertEquals(0L,File(dir,"ssr.rtcm3").length())
        assertTrue(runCatching {NtripCaptureStore(dir,NtripSettings(),{0L},{0L})}.isFailure)
    }
    @Test fun jsonEscapesControlCharactersAndKeepsIntegerNanoseconds() {
        assertEquals("\"a\\\"b\\\\c\\n\\t\"",captureJson("a\"b\\c\n\t"))
        assertEquals("1700000000000000000",captureJson(1700000000000000000L))
        assertTrue(runCatching {captureJson(Double.NaN)}.isFailure)
    }
    @Test fun whuThreeStreamArchiveKeepsIndependentBiasAndReceiptOrdering() {
        val dir=directory("whu_three");var elapsed=1000000000L;val wall=1700000000000000000L
        val settings=NtripSettings(correctionMount="SSRC00WHU0",centerOfMass=true,biasMount="OSBC00WHU1")
        val store=NtripCaptureStore(dir,settings,{wall+elapsed-1000000000L},{elapsed})
        val receipts=(0..2).map { channel -> elapsed+=1000000;store.event(channel,"CONNECTED");store.event(channel,"DATA",packet(listOf(1060,1019,1059)[channel])) }
        assertTrue(receipts.zipWithNext().all { (a,b)->a.seq<b.seq && a.elapsedNs<b.elapsedNs })
        assertEquals(1L,store.biasFrames())
        File(dir,"profile.txt").writeText("B_VERIFIED")
        val zip=store.finish(null,0,null,"USER_STOP")
        ZipFile(zip).use { z ->
            assertNotNull(z.getEntry("bias.rtcm3"));assertNotNull(z.getEntry("profile.txt"))
            val m=z.getInputStream(z.getEntry("capture.json")).bufferedReader().readText()
            assertTrue(m.contains("PPP_NTRIP_CAPTURE_V2"));assertTrue(m.contains("OSBC00WHU1"))
            assertTrue(m.contains("WHU_OSB_CONTINUITY_V1"))
            assertTrue(m.contains(captureDigest(File(dir,"profile.txt"))))
        }
        assertArrayEquals(packet(1059),File(dir,"bias.rtcm3").readBytes())
    }
    @Test fun optionalBiasMountCannotInjectHeadersOrReuseAnotherMount() {
        assertTrue(runCatching {NtripSettings(biasMount="a\r\nb").validate()}.isFailure)
        assertTrue(runCatching {NtripSettings(biasMount="BCEP00BKG0").validate()}.isFailure)
        val s=NtripSettings(correctionMount="SSRC00WHU0",biasMount="OSBC00WHU1",centerOfMass=true)
        assertTrue(String(NtripProtocol.request(s,s.biasMount,NtripCredentials("u","p"))).startsWith("GET /OSBC00WHU1 HTTP/1.1"))
    }
}
