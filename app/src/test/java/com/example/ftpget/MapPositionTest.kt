package com.example.ftpget

import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MapPositionTest {
    @Test fun markerRequestsWgs84ConversionWithLongitudeFirst() {
        val position = requireNotNull(MapPosition.device(39.993253, 116.473195))
        val uri = position.markerUri("设备定位")
        assertEquals("uri.amap.com", uri.host)
        assertEquals("/marker", uri.path)
        val params = uri.query.split('&')
        assertTrue("position=116.473195000,39.993253000" in params)
        assertTrue("coordinate=wgs84" in params)
        assertTrue("callnative=0" in params)
    }

    @Test fun shareRedirectFeedsConvertedCoordinatesToEmbeddedMap() {
        val redirect = URI("https://m.amap.com/share/index/lnglat=121.292,31.232&name=PPP&callnative=0")
        val embed = URI(requireNotNull(MapPosition.embedUrl(redirect, "实时 PPP")))
        assertEquals("www.amap.com", embed.host)
        assertEquals("/ssr/embed/place", embed.path)
        assertTrue("lng=121.292" in embed.query.split('&'))
        assertTrue("lat=31.232" in embed.query.split('&'))
        assertTrue("platform=pc" in embed.query.split('&'))
    }

    @Test fun rejectsUnexpectedShareDestinationsAndCoordinates() {
        assertNull(MapPosition.embedUrl(URI("https://example.com/share/index/lnglat=121,31"), "PPP"))
        assertNull(MapPosition.embedUrl(URI("https://m.amap.com/share/index/lnglat=NaN,31"), "PPP"))
        assertNull(MapPosition.embedUrl(URI("https://m.amap.com/share/index/lnglat=121,91"), "PPP"))
    }

    @Test fun liveMapRequiresAValidPppFix() {
        val result = LivePppResult(2442, 531605.0, 6, 17, 30.0, 104.0, 480.0,
            1.0, 2.0, 3.0, 0.1, 0.1, 0.1, 2.0, 60, 24, 19, 30)
        val point = requireNotNull(MapPosition.live(result))
        assertEquals(MapPosition.Source.LIVE_PPP, point.source)
        assertEquals(result.latitude, point.latitude, 0.0)
        assertEquals(result.longitude, point.longitude, 0.0)
        assertNull(MapPosition.live(result.copy(q = 0)))
        assertNull(MapPosition.live(result.copy(q = 5)))
        assertNull(MapPosition.live(result.copy(longitude = Double.NaN)))
    }

    @Test fun validPostprocessedRowRetainsRawCoordinates() {
        val columns = listOf("2026/10/31", "03:40:05.000", "30.0", "104.0", "480.0", "6")
        val point = requireNotNull(MapPosition.postprocessed(columns))
        assertEquals(MapPosition.Source.POSTPROCESSED_PPP, point.source)
        assertEquals(30.0, point.latitude, 0.0)
        assertEquals(104.0, point.longitude, 0.0)
        assertNull(MapPosition.postprocessed(columns.dropLast(1) + "0"))
    }
}
