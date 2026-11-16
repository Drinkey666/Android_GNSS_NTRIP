package com.example.ftpget.ui

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import android.text.TextUtils
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.example.ftpget.MapPosition
import com.example.ftpget.R
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.withContext

private enum class MapStatus { LOADING, READY, ERROR }
private const val REFRESH_INTERVAL_MS = 5_000L
private const val MAP_LOAD_TIMEOUT_MS = 20_000L

@Composable
internal fun AmapMap(position: MapPosition, sourceName: String) {
    var webView by remember { mutableStateOf<AmapWebView?>(null) }
    var status by remember { mutableStateOf(MapStatus.LOADING) }
    val latestPosition by rememberUpdatedState(position)
    val owner = LocalLifecycleOwner.current
    val mapTitle = stringResource(R.string.section_map)
    LaunchedEffect(webView, position.source, owner) {
        val view = webView ?: return@LaunchedEffect
        owner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            var first = true
            snapshotFlow { latestPosition }.conflate().collect {
                if (!first) {
                    delay(REFRESH_INTERVAL_MS)
                    // A new iframe recenters the viewport. Let the current gesture finish.
                    while (view.loading || view.recentlyTouched()) delay(250)
                }
                view.showPosition(latestPosition, sourceName, mapTitle)
                first = false
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
        AndroidView(
            factory = { context ->
                AmapWebView(context) { status = it }.also { webView = it }
            },
            modifier = Modifier.fillMaxSize(),
            onRelease = { it.release() },
        )
        when (status) {
            MapStatus.LOADING -> Surface(
                Modifier.align(Alignment.BottomCenter).padding(GnssSpacing.md),
                shape = MaterialTheme.shapes.small,
            ) {
                Row(
                    Modifier.padding(GnssSpacing.md),
                    horizontalArrangement = Arrangement.spacedBy(GnssSpacing.sm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    CircularProgressIndicator(Modifier.size(GnssSpacing.lg))
                    Text(stringResource(R.string.map_loading))
                }
            }
            MapStatus.ERROR -> Surface(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxSize()) {
                    MapMessage(
                        stringResource(R.string.map_load_error),
                        stringResource(R.string.map_load_hint),
                        Modifier.align(Alignment.Center),
                    )
                }
            }
            MapStatus.READY -> Unit
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
private class AmapWebView(context: Context, private val onStatus: (MapStatus) -> Unit) : WebView(context) {
    private var requestedPosition: MapPosition? = null
    private var cachedEmbed: Pair<MapPosition, String>? = null
    private var documentUrl: String? = null
    private var frameUrl: String? = null
    private var pageNumber = 0
    private var lastTouch: Long? = null
    private var status = MapStatus.LOADING
    val loading get() = status == MapStatus.LOADING
    private val timeout = Runnable { if (loading) setStatus(MapStatus.ERROR) }

    init {
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.setGeolocationEnabled(false)
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        isVerticalScrollBarEnabled = false
        isHorizontalScrollBarEnabled = false
        setOnTouchListener { _, _ ->
            lastTouch = SystemClock.elapsedRealtime()
            false
        }
        webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                request.isForMainFrame || request.url.scheme != "https"

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                checkLoadError(request)
            }

            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, response: WebResourceResponse) {
                checkLoadError(request)
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (url == documentUrl && loading) setStatus(MapStatus.READY)
            }
        }
    }

    fun recentlyTouched(): Boolean =
        lastTouch?.let { SystemClock.elapsedRealtime() - it < REFRESH_INTERVAL_MS } == true

    suspend fun showPosition(position: MapPosition, name: String, title: String) {
        if (position == requestedPosition && status != MapStatus.ERROR) return
        requestedPosition = null
        documentUrl = null
        frameUrl = null
        removeCallbacks(timeout)
        stopLoading()
        setStatus(MapStatus.LOADING)

        val userAgent = settings.userAgentString
        val embed = try {
            cachedEmbed?.takeIf { it.first == position }?.second ?: withContext(Dispatchers.IO) {
                position.loadEmbedUrl(name, userAgent)
            }
        } catch (_: IOException) {
            setStatus(MapStatus.ERROR)
            return
        } catch (_: IllegalArgumentException) {
            setStatus(MapStatus.ERROR)
            return
        }
        requestedPosition = position
        cachedEmbed = position to embed
        frameUrl = embed
        pageNumber++
        val wrapper = "https://appassets.androidplatform.net/amap/$pageNumber"
        documentUrl = wrapper
        val escapedUrl = TextUtils.htmlEncode(embed)
        val escapedTitle = TextUtils.htmlEncode(title)
        val html = """
            <!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
              html,body{margin:0;overflow:hidden}
              iframe{display:block;width:100%;border:0}
            </style>
            </head><body><iframe src="$escapedUrl" title="$escapedTitle"
              referrerpolicy="strict-origin-when-cross-origin"></iframe>
            <script>
              const mapFrame = document.querySelector('iframe');
              const resizeMap = () => { mapFrame.style.height = window.innerHeight + 'px'; };
              window.addEventListener('resize', resizeMap);
              resizeMap();
            </script></body></html>
        """.trimIndent()
        loadDataWithBaseURL(wrapper, html, "text/html", "utf-8", null)
        postDelayed(timeout, MAP_LOAD_TIMEOUT_MS)
    }

    private fun checkLoadError(request: WebResourceRequest) {
        val url = request.url.toString()
        if (url == documentUrl || url == frameUrl) setStatus(MapStatus.ERROR)
    }

    private fun setStatus(value: MapStatus) {
        status = value
        if (!loading) removeCallbacks(timeout)
        onStatus(value)
    }

    fun release() {
        removeCallbacks(timeout)
        stopLoading()
        destroy()
    }
}
