package com.example.ftpget.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.ftpget.NtripSettings
import com.example.ftpget.R

@Composable
internal fun NtripSection(state: MainUiState, compact: Boolean = false) {
    var editing by remember { mutableStateOf(false) }
    var expanded by rememberSaveable { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(GnssSpacing.md)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.ntrip_title),
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2, overflow = TextOverflow.Ellipsis)
            TextButton(onClick = { editing = true }, enabled = !state.ntripRunning) {
                Text(stringResource(R.string.ntrip_settings))
            }
        }
        Surface(color = if (compact) MaterialTheme.colorScheme.surfaceVariant
                else MaterialTheme.colorScheme.primaryContainer,
            shape = MaterialTheme.shapes.medium) {
            Column(Modifier.fillMaxWidth().padding(GnssSpacing.lg),
                verticalArrangement = Arrangement.spacedBy(GnssSpacing.md)) {
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(GnssSpacing.sm)) {
                    Box(Modifier.size(8.dp).background(
                        if (state.captureActive) MaterialTheme.colorScheme.secondary
                        else MaterialTheme.colorScheme.outline, CircleShape))
                    Text(stringResource(if (state.captureActive) R.string.ntrip_recording
                        else R.string.ntrip_standby),
                        style = MaterialTheme.typography.labelMedium,
                        color = if (compact) MaterialTheme.colorScheme.onSurfaceVariant
                        else MaterialTheme.colorScheme.onPrimaryContainer)
                }
                Text(if (state.captureActive && state.captureMessage.text.isNotBlank())
                    state.captureMessage.text else state.ntripDataStatus.text,
                    style = MaterialTheme.typography.titleMedium,
                    color = if (compact) MaterialTheme.colorScheme.onSurface
                    else MaterialTheme.colorScheme.onPrimaryContainer,
                    maxLines = 3, overflow = TextOverflow.Ellipsis)
                Text(stringResource(R.string.ntrip_endpoint,
                    state.ntripSettings.host, state.ntripSettings.port),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (compact) MaterialTheme.colorScheme.onSurfaceVariant
                    else MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.75f),
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (!state.captureActive) {
                    Button(onClick = state.onCaptureStart,
                        enabled = !state.ntripRunning && !state.atmosphereBusy,
                        modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small) {
                        Text(stringResource(R.string.capture_start))
                    }
                } else {
                    FilledTonalButton(onClick = state.onCaptureStop,
                        enabled = !state.captureStopping,
                        modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small) {
                        Text(stringResource(R.string.capture_stop))
                    }
                }
            }
        }
        if (!compact) {
            Column(verticalArrangement = Arrangement.spacedBy(GnssSpacing.xs)) {
                StreamStatus(state.ntripSsrStatus.text)
                StreamStatus(state.ntripNavStatus.text)
                StreamStatus(state.ntripBiasStatus.text.ifBlank {
                    stringResource(R.string.capture_bias_status,
                        stringResource(R.string.ntrip_disconnected))
                })
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = state.onPrepareAtmosphere,
                enabled = !state.captureActive && !state.atmosphereBusy) {
                if (state.atmosphereBusy) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(GnssSpacing.sm))
                }
                Text(stringResource(R.string.capture_atmosphere))
            }
            TextButton(onClick = { expanded = !expanded }) {
                Text(stringResource(if (expanded) R.string.show_less else R.string.show_more))
            }
        }
        if (expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(GnssSpacing.sm)) {
                if (compact) {
                    StreamStatus(state.ntripSsrStatus.text)
                    StreamStatus(state.ntripNavStatus.text)
                    StreamStatus(state.ntripBiasStatus.text.ifBlank {
                        stringResource(R.string.capture_bias_status,
                            stringResource(R.string.ntrip_disconnected))
                    })
                }
                DetailText(stringResource(R.string.capture_ssr_label,
                    state.ntripSettings.correctionMount))
                DetailText(stringResource(R.string.capture_nav_label,
                    state.ntripSettings.navigationMount))
                DetailText(stringResource(R.string.capture_bias_label,
                    state.ntripSettings.biasMount))
                DetailText(stringResource(R.string.capture_bytes, state.captureBytes / 1024.0))
                DetailText(stringResource(R.string.capture_frames,
                    state.captureSsrFrames, state.captureNavFrames))
                DetailText(stringResource(R.string.capture_bias_frames,
                    state.captureBiasFrames))
                DetailText(state.captureMessage.text)
                state.captureArchive?.let {
                    DetailText(stringResource(R.string.capture_latest_archive,
                        java.io.File(it).name))
                }
                TextButton(onClick = state.onCaptureExport,
                    enabled = !state.captureActive && !state.captureExportBusy &&
                        state.captureArchive != null) {
                    Text(stringResource(R.string.capture_export))
                }
                TextButton(onClick = { state.btnChooseExportDirectory.click() },
                    enabled = !state.captureActive) {
                    Text(stringResource(R.string.capture_choose_folder))
                }
                DetailText(stringResource(R.string.capture_stream_help))
                DetailText(stringResource(R.string.capture_workflow))
                DetailText(stringResource(R.string.ntrip_explanation))
            }
        }
    }
    if (editing) NtripEditor(state, onDismiss = { editing = false })
}

@Composable
private fun StreamStatus(status: String) {
    Row(verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(GnssSpacing.sm)) {
        Box(Modifier.size(6.dp).background(
            if (status.contains("已连接") || status.contains("接收"))
                MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
            CircleShape))
        Text(status, style = MaterialTheme.typography.bodySmall,
            color = statusColor(status), maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NtripEditor(state: MainUiState, onDismiss: () -> Unit) {
    val initial = state.ntripSettings
    var host by remember { mutableStateOf(initial.host) }
    var port by remember { mutableStateOf(initial.port.toString()) }
    var ssr by remember { mutableStateOf(initial.correctionMount) }
    var bias by remember { mutableStateOf(initial.biasMount) }
    var nav by remember { mutableStateOf(initial.navigationMount) }
    var tls by remember { mutableStateOf(initial.tls) }
    var com by remember { mutableStateOf(initial.centerOfMass) }
    var user by remember { mutableStateOf(state.ntripUser) }
    // Deliberately not rememberSaveable: credentials are session-only, never backup/state/log.
    var password by remember { mutableStateOf(state.ntripPassword) }
    var invalid by remember { mutableStateOf(false) }
    val save = {
            val proposed = NtripSettings(host.trim(), port.toIntOrNull() ?: 0, ssr.trim(), nav.trim(), tls, com, bias.trim())
            if (runCatching { proposed.validate() }.isFailure || user.contains(':') ||
                user.any { it == '\r' || it == '\n' } || password.any { it == '\r' || it == '\n' }) {
                invalid = true
            } else {
                state.ntripSettings = proposed; state.ntripUser = user; state.ntripPassword = password
                state.onNtripSettingsChanged(proposed); onDismiss()
            }
    }
    ModalBottomSheet(onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().fillMaxHeight(0.92f).imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = GnssSpacing.screen)
            .padding(bottom = GnssSpacing.xxl),
            verticalArrangement = Arrangement.spacedBy(GnssSpacing.md)) {
            Text(stringResource(R.string.ntrip_settings),
                style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.ntrip_connection_group),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary)
            OutlinedTextField(host, { host = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_host)) }, singleLine = true)
            OutlinedTextField(port, { port = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_port)) }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            OutlinedTextField(ssr, { ssr = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_ssr_mount)) }, singleLine = true)
            OutlinedTextField(bias, { bias = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_bias_mount)) }, singleLine = true)
            OutlinedTextField(nav, { nav = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_nav_mount)) }, singleLine = true)
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Text(stringResource(R.string.ntrip_account_group),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary)
            OutlinedTextField(user, { user = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_user)) }, singleLine = true)
            OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.ntrip_password)) }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
            DetailText(stringResource(R.string.ntrip_password_memory))
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.ntrip_tls),
                    style = MaterialTheme.typography.bodyMedium)
                Switch(tls, { tls = it })
            }
            Text(stringResource(R.string.ntrip_datum),
                style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(GnssSpacing.sm)) {
                FilterChip(com, { com = true }, label = { Text("CoM") })
                FilterChip(!com, { com = false }, label = { Text("APC") })
            }
            if (invalid) Text(stringResource(R.string.ntrip_invalid),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(GnssSpacing.sm)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text(stringResource(R.string.reference_cancel))
                }
                Button(onClick = save, modifier = Modifier.weight(1f)) {
                    Text(stringResource(R.string.ntrip_save_settings))
                }
            }
        }
    }
}
