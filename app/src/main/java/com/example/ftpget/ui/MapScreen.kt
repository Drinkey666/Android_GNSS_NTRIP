package com.example.ftpget.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import com.example.ftpget.MapPosition
import com.example.ftpget.R

@Composable
fun MapPage(state: MainUiState, modifier: Modifier = Modifier) {
    val position = state.mapSolution ?: state.positionFix?.let {
        MapPosition.device(it.latitude, it.longitude)
    }
    val source = stringResource(when (position?.source) {
        MapPosition.Source.LIVE_PPP -> R.string.map_source_live
        MapPosition.Source.POSTPROCESSED_PPP -> R.string.map_source_post
        else -> R.string.section_position
    })
    Column(modifier.fillMaxSize()) {
        Surface(
            modifier = Modifier.fillMaxWidth().padding(
                horizontal = GnssSpacing.screen,
                vertical = GnssSpacing.sm,
            ),
            shape = MaterialTheme.shapes.small,
            color = MaterialTheme.colorScheme.surfaceContainer,
        ) {
            Column(
                Modifier.padding(horizontal = GnssSpacing.md, vertical = GnssSpacing.sm),
                verticalArrangement = Arrangement.spacedBy(GnssSpacing.xs),
            ) {
                Text(
                    stringResource(R.string.map_current_source, source),
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    if (position == null) stringResource(R.string.map_waiting_fix)
                    else stringResource(R.string.map_coordinates, position.latitude, position.longitude),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Box(Modifier.fillMaxWidth().weight(1f)) {
            when {
                position == null -> MapMessage(
                    stringResource(R.string.map_waiting_fix),
                    stringResource(R.string.map_waiting_hint),
                    Modifier.align(Alignment.Center),
                )
                LocalInspectionMode.current -> MapMessage(
                    stringResource(R.string.section_map),
                    stringResource(R.string.preview_map),
                    Modifier.align(Alignment.Center),
                )
                else -> AmapMap(position, source)
            }
        }
    }
}

@Composable
internal fun MapMessage(title: String, detail: String, modifier: Modifier = Modifier) {
    Column(
        modifier.padding(GnssSpacing.xl),
        verticalArrangement = Arrangement.spacedBy(GnssSpacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(
            detail,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Preview(showBackground = true, name = "MAP · Light")
@Composable private fun MapLightPreview() {
    GnssTheme {
        MapPage(remember { MainUiState().apply {
            positionFix = PositionFix(39.9042, 116.4074, 43.0, 2.4f)
        } })
    }
}

@Preview(showBackground = true, name = "MAP · Dark")
@Composable private fun MapDarkPreview() {
    GnssTheme(darkTheme = true) { MapPage(remember { MainUiState() }) }
}
