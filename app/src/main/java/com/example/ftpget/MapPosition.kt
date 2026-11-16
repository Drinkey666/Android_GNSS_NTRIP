package com.example.ftpget

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLEncoder
import java.util.Locale

/** The coordinates in this display model are always the original WGS84 values. */
@ConsistentCopyVisibility
internal data class MapPosition private constructor(
    val latitude: Double,
    val longitude: Double,
    val source: Source,
) {
    enum class Source { DEVICE, LIVE_PPP, POSTPROCESSED_PPP }

    fun markerUri(name: String): URI {
        val position = String.format(Locale.US, "%.9f,%.9f", longitude, latitude)
        return URI("https://uri.amap.com/marker?position=$position&name=${encode(name)}" +
            "&coordinate=wgs84&callnative=0&src=com.example.pppntrip")
    }

    fun loadEmbedUrl(name: String, userAgent: String): String {
        var endpoint = markerUri(name)
        repeat(2) {
            val connection = endpoint.toURL().openConnection() as HttpURLConnection
            val redirect = try {
                connection.instanceFollowRedirects = false
                connection.connectTimeout = 6_000
                connection.readTimeout = 6_000
                connection.setRequestProperty("User-Agent", userAgent)
                if (connection.responseCode !in 300..399) throw IOException("AMap conversion did not redirect")
                connection.getHeaderField("Location") ?: throw IOException("AMap conversion has no redirect")
            } finally {
                connection.disconnect()
            }
            val target = endpoint.resolve(redirect)
            embedUrl(target, name)?.let { return it }
            if (target.scheme != "https" || target.host != "ditu.amap.com" || target.path != "/regeo") {
                throw IOException("Unexpected AMap conversion destination")
            }
            endpoint = target
        }
        throw IOException("AMap conversion returned no coordinates")
    }

    companion object {
        fun device(latitude: Double, longitude: Double) =
            create(latitude, longitude, Source.DEVICE)

        fun live(result: LivePppResult): MapPosition? =
            if (result.q == 6 && result.height.isFinite()) {
                create(result.latitude, result.longitude, Source.LIVE_PPP)
            } else null

        fun postprocessed(columns: List<String>): MapPosition? {
            val quality = columns.getOrNull(5)?.toIntOrNull() ?: return null
            if (quality !in 1..7 ||
                columns[4].toDoubleOrNull()?.isFinite() != true) return null
            val latitude = columns[2].toDoubleOrNull() ?: return null
            val longitude = columns[3].toDoubleOrNull() ?: return null
            return create(latitude, longitude, Source.POSTPROCESSED_PPP)
        }

        fun embedUrl(redirect: URI, name: String): String? {
            if (redirect.scheme != "https" || redirect.host != "m.amap.com") return null
            val prefix = "/share/index/lnglat="
            val path = redirect.path ?: return null
            if (!path.startsWith(prefix)) return null
            val coordinates = path.removePrefix(prefix).substringBefore('&').split(',')
            if (coordinates.size != 2) return null
            val longitude = coordinates[0].toDoubleOrNull() ?: return null
            val latitude = coordinates[1].toDoubleOrNull() ?: return null
            if (!validCoordinates(latitude, longitude)) return null
            return "https://www.amap.com/ssr/embed/place?lng=$longitude&lat=$latitude" +
                "&name=${encode(name)}&zoom=17&platform=pc&src=com.example.pppntrip"
        }

        private fun create(latitude: Double, longitude: Double, source: Source) =
            if (validCoordinates(latitude, longitude)) MapPosition(latitude, longitude, source) else null

        private fun validCoordinates(latitude: Double, longitude: Double) =
            latitude in -90.0..90.0 && longitude in -180.0..180.0

        private fun encode(name: String) = URLEncoder.encode(name, "UTF-8")
    }
}
