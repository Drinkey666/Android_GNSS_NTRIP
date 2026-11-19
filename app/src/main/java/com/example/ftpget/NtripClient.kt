package com.example.ftpget

import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.util.Base64
import java.util.Locale
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

internal const val WHU_SSR_PROFILE = "WHU_OSB_FIRST_COMPLETE_V2"

/** Not a data class: generated toString/copy must never expose a password. */
class NtripCredentials(val user: String, val password: String) {
    override fun toString() = "NtripCredentials(REDACTED)"
}

data class NtripSettings(
    val host: String = "ntrip.gnsslab.cn", val port: Int = 2101,
    val correctionMount: String = "SSRA00BKG0", val navigationMount: String = "BCEP00BKG0",
    val tls: Boolean = false, val centerOfMass: Boolean = false,
    val biasMount: String = "",
) {
    fun validate() {
        require(host.matches(Regex("[A-Za-z0-9.-]+")) && !host.startsWith('.') && host.length <= 253) {
            "HOST_INVALID"
        }
        require(port in 1..65535) { "PORT_INVALID" }
        for (mount in listOf(correctionMount, navigationMount) + listOf(biasMount).filter { it.isNotEmpty() }) {
            require(mount.matches(Regex("[A-Za-z0-9_.-]{1,128}"))) { "MOUNT_INVALID" }
        }
        require(listOf(correctionMount,navigationMount,biasMount).filter { it.isNotEmpty() }.distinct().size == if(biasMount.isEmpty()) 2 else 3) { "MOUNTS_MUST_DIFFER" }
    }
}

/** Strict NTRIP v2 HTTP plus legacy ICY. Never follows redirects or logs request/auth. */
internal object NtripProtocol {
    fun request(settings: NtripSettings, mount: String, credentials: NtripCredentials): ByteArray {
        settings.validate()
        require(mount == settings.correctionMount || mount == settings.navigationMount || mount == settings.biasMount)
        require(credentials.user.none { it == ':' || it == '\r' || it == '\n' })
        require(credentials.password.none { it == '\r' || it == '\n' })
        val authorization = if (credentials.user.isNotEmpty()) "Authorization: Basic " +
            Base64.getEncoder().encodeToString((credentials.user + ":" + credentials.password)
                .toByteArray(StandardCharsets.UTF_8)) + "\r\n" else ""
        return ("GET /$mount HTTP/1.1\r\nHost: ${settings.host}:${settings.port}\r\n" +
            "Ntrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP PPP-NTRIP/1.0\r\n" +
            "Accept: gnss/data, application/octet-stream\r\nAccept-Encoding: identity\r\n" +
            authorization + "Connection: close\r\n\r\n").toByteArray(StandardCharsets.US_ASCII)
    }
    private fun line(input: InputStream, limit: Int): String {
        val out = ByteArrayOutputStream()
        while (true) {
            val b = input.read()
            if (b < 0) throw EOFException("NTRIP_HEADER_EOF")
            if (b == 10) return out.toString("US-ASCII").trimEnd('\r')
            if (out.size() >= limit) error("NTRIP_HEADER_TOO_LARGE")
            out.write(b)
        }
    }
    fun body(input: BufferedInputStream, onStatusOk: () -> Unit = {}): InputStream {
        val status = line(input, 1024)
        if (status.startsWith("SOURCETABLE")) error("NTRIP_SOURCETABLE_NOT_CORRECTION")
        val words = status.split(' ')
        require(words.size >= 2 && words[1] == "200" &&
            (words[0] == "ICY" || words[0].startsWith("HTTP/1."))) { "NTRIP_HTTP_${words.getOrNull(1)?.take(3) ?: "INVALID"}" }
        onStatusOk()
        val headers = linkedMapOf<String, String>()
        var bytes = status.length
        // Some v1 casters send only ICY + CRLF, immediately followed by RTCM.
        input.mark(1); val first = input.read(); input.reset()
        if (words[0] == "ICY" && first == 0xD3) return input
        while (true) {
            val next = line(input, 4096); bytes += next.length + 2
            require(bytes <= 16384) { "NTRIP_HEADER_TOO_LARGE" }
            if (next.isEmpty()) break
            val at = next.indexOf(':'); require(at > 0) { "NTRIP_BAD_HEADER" }
            val name = next.substring(0, at).trim().lowercase(Locale.US)
            require(name !in headers) { "NTRIP_DUPLICATE_HEADER" }
            headers[name] = next.substring(at + 1).trim()
        }
        require(!headers["content-type"].orEmpty().lowercase(Locale.US).contains("text")) {
            "NTRIP_TEXT_NOT_CORRECTION"
        }
        require(headers["content-encoding"].orEmpty().lowercase(Locale.US) in listOf("", "identity")) {
            "NTRIP_UNSUPPORTED_ENCODING"
        }
        val transfer = headers["transfer-encoding"].orEmpty().lowercase(Locale.US)
        return when (transfer) {
            "" -> input
            "chunked" -> Chunked(input)
            else -> error("NTRIP_UNSUPPORTED_TRANSFER")
        }
    }
    private class Chunked(val source: InputStream) : InputStream() {
        var left = 0L; var ended = false; var needTerminator = false
        override fun read(): Int {
            val b = ByteArray(1); return if (read(b, 0, 1) < 0) -1 else b[0].toInt() and 255
        }
        override fun read(b: ByteArray, off: Int, len: Int): Int {
            if (len == 0) return 0
            if (ended) return -1
            if (left == 0L) {
                if (needTerminator) require(line(source, 2).isEmpty()) { "NTRIP_BAD_CHUNK_END" }
                val size = line(source, 128).substringBefore(';').trim()
                require(size.matches(Regex("[0-9a-fA-F]{1,8}"))) { "NTRIP_BAD_CHUNK" }
                left = size.toLong(16); require(left <= 8 * 1024 * 1024) { "NTRIP_CHUNK_TOO_LARGE" }
                if (left == 0L) {
                    var count = 0
                    while (line(source, 1024).isNotEmpty()) { require(++count <= 16) }
                    ended = true; return -1
                }
                needTerminator = true
            }
            val n = source.read(b, off, minOf(len.toLong(), left).toInt())
            if (n < 0) throw EOFException("NTRIP_CHUNK_TRUNCATED")
            left -= n; return n
        }
    }
}

/** Each stream has its own 404 retry budget, including before its first payload. */
internal class NtripReconnectPolicy(private val max404Retries:Int=3) {
    private var retries=0
    fun received() { retries=0 }
    fun failure(status:String):String {
        if(status=="NTRIP_HTTP_404" && retries<max404Retries)
            return "RETRY_HTTP_404_${++retries}"
        return status
    }
}

/** Socket worker. Reconnects after transport failures; shutdown closes a blocked read. */
class NtripClient(
    private val settings: NtripSettings, private val mount: String,
    private val credentials: NtripCredentials,
    private val onConnect: () -> Unit,
    private val onBytes: (ByteArray) -> Unit,
    private val onStatus: (String) -> Unit,
) {
    @Volatile private var active = false
    @Volatile private var socket: Socket? = null
    private var worker: Thread? = null
    @Synchronized fun start() {
        if (active) return
        settings.validate(); active = true
        worker = Thread({
            var delay = 1000L
            val reconnect=NtripReconnectPolicy()
            while (active) {
                var stage = "DNS"
                try {
                    onStatus("CONNECTING")
                    val plain = Socket(); socket = plain
                    if (!active) { plain.close(); break }
                    val endpoint = InetSocketAddress(java.net.InetAddress.getByName(settings.host), settings.port)
                    stage = "TCP_CONNECT"
                    plain.connect(endpoint, 10000)
                    plain.soTimeout = 15000
                    val streamSocket = if (settings.tls) {
                        stage = "TLS_HANDSHAKE"
                        (SSLSocketFactory.getDefault() as SSLSocketFactory)
                            .createSocket(plain, settings.host, settings.port, true).let { it as SSLSocket }.apply {
                                sslParameters = sslParameters.apply { endpointIdentificationAlgorithm = "HTTPS" }
                                socket = this
                                if (!active) { close(); throw InterruptedException() }
                                startHandshake()
                            }
                    } else plain
                    stage = "REQUEST_WRITE"
                    streamSocket.getOutputStream().apply {
                        write(NtripProtocol.request(settings, mount, credentials)); flush()
                    }
                    stage = "STATUS_LINE"
                    val body = NtripProtocol.body(BufferedInputStream(streamSocket.getInputStream())) {
                        stage = "RESPONSE_HEADERS"
                    }
                    stage = "BODY_READ"
                    onConnect(); onStatus("CONNECTED_WAITING_RTCM")
                    val buffer = ByteArray(8192)
                    while (active) {
                        val n = body.read(buffer)
                        if (n < 0) throw EOFException()
                        if (n > 0) { onBytes(buffer.copyOf(n)); reconnect.received(); delay = 1000 }
                    }
                } catch (e: Exception) {
                    // Do not echo arbitrary remote response, URL, request or credentials.
                    val safe = e.message?.takeIf { it.matches(Regex("NTRIP_[A-Z0-9_]+")) }
                    val status=reconnect.failure(safe ?: "NETWORK_DISCONNECTED_${stage}_${e.javaClass.simpleName}")
                    if (active) onStatus(status)
                    if (status.startsWith("NTRIP_HTTP_4") || status == "NTRIP_SOURCETABLE_NOT_CORRECTION") {
                        active = false // a credential/mount error cannot be solved by repeated requests
                    }
                } finally {
                    try { socket?.close() } catch (_: Exception) { }
                    socket = null
                }
                if (active) try { Thread.sleep(delay); delay = minOf(delay * 2, 30000) }
                catch (_: InterruptedException) { }
            }
        }, "NTRIP-stream").apply { isDaemon = true; start() }
    }
    fun stop() {
        active = false
        try { socket?.close() } catch (_: Exception) { }
        worker?.interrupt()
    }
    /** Call off the main thread before closing capture files. */
    fun awaitStopped(timeoutMillis: Long = 20000): Boolean {
        val t = worker ?: return true
        check(t !== Thread.currentThread())
        t.join(timeoutMillis)
        return !t.isAlive
    }
}
