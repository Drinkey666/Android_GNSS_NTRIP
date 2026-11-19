package com.example.ftpget

import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayInputStream
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class NtripProtocolTest {
    @Test fun initial404RetriesAreBounded() {
        val policy = NtripReconnectPolicy()
        for (attempt in 1..3) assertEquals("RETRY_HTTP_404_$attempt", policy.failure("NTRIP_HTTP_404"))
        assertEquals("NTRIP_HTTP_404", policy.failure("NTRIP_HTTP_404"))
    }
    @Test fun workingMount404RetriesAreBounded() {
        val p=NtripReconnectPolicy();p.received()
        for(i in 1..3)assertEquals("RETRY_HTTP_404_$i",p.failure("NTRIP_HTTP_404"))
        assertEquals("NTRIP_HTTP_404",p.failure("NTRIP_HTTP_404"))
    }
    @Test fun successfulDataResetsReconnectBudget() {
        val p=NtripReconnectPolicy();p.received();p.failure("NTRIP_HTTP_404");p.received()
        assertEquals("RETRY_HTTP_404_1",p.failure("NTRIP_HTTP_404"))
    }
    @Test fun authorizationErrorsNeverRetry() {
        val p=NtripReconnectPolicy();p.received()
        for(s in listOf("NTRIP_HTTP_401","NTRIP_HTTP_403"))assertEquals(s,p.failure(s))
    }
    @Test fun socketRecoversFromInitialAndLater404() {
        ServerSocket(0).use { server ->
            val done=CountDownLatch(1)
            val error=AtomicReference<Throwable?>()
            val counts=java.util.concurrent.atomic.AtomicInteger()
            val statuses=java.util.concurrent.CopyOnWriteArrayList<String>()
            val peer=Thread {
                try {
                    repeat(4) { attempt -> server.accept().use { socket ->
                        val reader=socket.getInputStream().bufferedReader()
                        while(!reader.readLine().isNullOrEmpty()) { }
                        socket.getOutputStream().apply {
                            if(attempt==0 || attempt==2)write("HTTP/1.1 404 Not Found\r\n\r\n".toByteArray())
                            else {write("HTTP/1.1 200 OK\r\n\r\n".toByteArray());write(payload)}
                            flush()
                        }
                    } }
                } catch(t:Throwable) {error.set(t);done.countDown()}
            }.apply {isDaemon=true;start()}
            val client=NtripClient(NtripSettings(host="localhost",port=server.localPort),"SSRA00BKG0",
                NtripCredentials("",""),{}, {if(counts.incrementAndGet()==2)done.countDown()}, {statuses+=it})
            try {client.start();assertTrue(done.await(9,TimeUnit.SECONDS))}
            finally {client.stop();assertTrue(client.awaitStopped(2500))}
            peer.join(1000);assertNull(error.get());assertEquals(2,counts.get())
            assertEquals(2, statuses.count { it == "RETRY_HTTP_404_1" })
            assertFalse(statuses.contains("NTRIP_HTTP_404"))
        }
    }
    private val payload = byteArrayOf(0xD3.toByte(), 0, 2, 0x41, 0, 4, 5, 6)
    private fun parse(header: String, data: ByteArray = payload) =
        NtripProtocol.body(ByteArrayInputStream(header.toByteArray() + data).buffered()).readBytes()
    private fun fails(block: () -> Unit) { assertTrue(runCatching(block).isFailure) }

    @Test fun normalHttpPreservesBinary() {
        assertArrayEquals(payload, parse("HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\n\r\n"))
    }
    @Test fun icyWithoutHeadersPreservesFirstRtcmByte() {
        assertArrayEquals(payload, parse("ICY 200 OK\r\n"))
    }
    @Test fun icyWithBlankLineOrHeaders() {
        assertArrayEquals(payload, parse("ICY 200 OK\r\n\r\n"))
        assertArrayEquals(payload, parse("ICY 200 OK\r\nServer: caster\r\n\r\n"))
    }
    @Test fun chunkedAcrossBinaryBoundaries() {
        val b = "3\r\n".toByteArray() + payload.take(3).toByteArray() + "\r\n5;foo=bar\r\n".toByteArray() +
            payload.drop(3).toByteArray() + "\r\n0\r\nX-Test: ok\r\n\r\n".toByteArray()
        assertArrayEquals(payload, parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n", b))
    }
    @Test fun badResponsesNeverReachDecoder() {
        for (h in listOf("HTTP/1.1 401 Unauthorized\r\n", "HTTP/1.1 302 Found\r\n",
            "SOURCETABLE 200 OK\r\n", "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n",
            "HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\n")) fails { parse(h) }
    }
    @Test fun boundsAndMalformedChunk() {
        fails { parse("HTTP/1.1 200 OK\r\nX: ${"x".repeat(5000)}\r\n\r\n") }
        fails { parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n", "zz\r\n".toByteArray()) }
        fails { parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n", "8\r\na".toByteArray()) }
    }
    @Test fun requestAndSecretRedaction() {
        val credentials = NtripCredentials("test-user", "not-a-real-password")
        val req = NtripProtocol.request(NtripSettings(), "SSRA00BKG0", credentials).decodeToString()
        assertTrue(req.startsWith("GET /SSRA00BKG0 HTTP/1.1\r\n"))
        assertTrue(req.contains("Authorization: Basic "))
        assertFalse(credentials.toString().contains(credentials.password))
        fails { NtripProtocol.request(NtripSettings(), "SSRA00BKG0", NtripCredentials("a\r\nb", "x")) }
    }
    @Test fun independentNavigationUsesPublicHostWithoutSharingCredentials() {
        val settings = NtripSettings(correctionMount="SSRC00WHU0", biasMount="OSBC00WHU1",
            useSnipBroadcast=true)
        val auth = NtripCredentials("test-user", "test-password")
        val nav = NtripProtocol.request(settings, settings.activeNavigationMount, auth).decodeToString()
        assertTrue(nav.startsWith("GET /RTCM3EPH HTTP/1.1\r\nHost: ntrip.use-snip.com:2101\r\n"))
        assertFalse(nav.contains("Authorization:"))
        for (mount in listOf(settings.correctionMount, settings.biasMount)) {
            val req = NtripProtocol.request(settings, mount, auth).decodeToString()
            assertTrue(req.contains("Host: ntrip.gnsslab.cn:2101\r\n"))
            assertTrue(req.contains("Authorization: Basic "))
        }
        fails { settings.copy(correctionMount=SNIP_MOUNT).validate() }
        assertEquals(settings.navigationMount, settings.copy(useSnipBroadcast=false).activeNavigationMount)
    }
    @Test fun settingsRejectInjectionAndAmbiguousEndpoints() {
        for (s in listOf(NtripSettings(host="http://example.com"), NtripSettings(port=0),
            NtripSettings(correctionMount="foo\r\nX: bar"), NtripSettings(navigationMount="SSRA00BKG0"))) {
            fails { s.validate() }
        }
        NtripSettings(host="localhost", port=443, tls=true).validate()
    }
    @Test fun actualSocketReadAndStop() {
        ServerSocket(0).use { server ->
            val arrived = CountDownLatch(1); val bytes = AtomicReference<ByteArray>()
            val service = Thread {
                server.accept().use { socket ->
                    socket.soTimeout=2000
                    val reader = socket.getInputStream().bufferedReader()
                    while (!reader.readLine().isNullOrEmpty()) { }
                    socket.getOutputStream().apply {
                        write("HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\n\r\n".toByteArray()); write(payload); flush()
                    }
                    try { socket.getInputStream().read() } catch (_: Exception) { }
                }
            }.apply { isDaemon=true; start() }
            val client = NtripClient(NtripSettings(host="localhost", port=server.localPort), "SSRA00BKG0",
                NtripCredentials("", ""), {}, { bytes.set(it); arrived.countDown() }, {})
            try { client.start(); assertTrue(arrived.await(5, TimeUnit.SECONDS)); assertArrayEquals(payload, bytes.get()) }
            finally { client.stop(); assertTrue(client.awaitStopped(2500)) }
            service.join(2000); assertFalse(service.isAlive)
        }
    }
    @Test fun unauthorizedStopsWithoutRetryLoop() {
        ServerSocket(0).use { server ->
            val failure = CountDownLatch(1)
            val service = Thread {
                server.accept().use {
                    it.soTimeout=2000
                    val reader=it.getInputStream().bufferedReader()
                    while(!reader.readLine().isNullOrEmpty()) { }
                    it.getOutputStream().apply { write("HTTP/1.1 401 Unauthorized\r\n\r\n".toByteArray()); flush() }
                }
            }.apply { isDaemon=true; start() }
            val client = NtripClient(NtripSettings(host="localhost", port=server.localPort), "SSRA00BKG0",
                NtripCredentials("", ""), {}, {}, { if (it == "NTRIP_HTTP_401") failure.countDown() })
            try { client.start(); assertTrue(failure.await(5, TimeUnit.SECONDS)) } finally { client.stop(); assertTrue(client.awaitStopped(2500)) }
            service.join(2000)
        }
    }
}
