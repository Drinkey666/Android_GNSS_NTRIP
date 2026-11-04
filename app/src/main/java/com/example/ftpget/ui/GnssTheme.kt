package com.example.ftpget.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val LightColors = lightColorScheme(
    primary = Color(0xFF1B6797),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCEFFA),
    onPrimaryContainer = Color(0xFF113F5D),
    secondary = Color(0xFF147B84),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD2F0ED),
    onSecondaryContainer = Color(0xFF174C51),
    tertiary = Color(0xFF916A3F),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFF7EAD6),
    onTertiaryContainer = Color(0xFF583D20),
    background = Color(0xFFF5FAFD),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFEAF3F9),
    onSurface = Color(0xFF172B3A),
    onSurfaceVariant = Color(0xFF607588),
    outline = Color(0xFF7891A3),
    outlineVariant = Color(0xFFD6E5EF),
    error = Color(0xFFB3261E),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    surfaceTint = Color(0xFF1B6797),
    inverseSurface = Color(0xFF223541),
    inverseOnSurface = Color(0xFFEAF4F9),
    inversePrimary = Color(0xFF9CCFF0),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFF9CCFF0),
    onPrimary = Color(0xFF07344E),
    primaryContainer = Color(0xFF173D57),
    onPrimaryContainer = Color(0xFFD6ECFA),
    secondary = Color(0xFF7BD0C7),
    onSecondary = Color(0xFF093C3A),
    secondaryContainer = Color(0xFF1E4B4E),
    onSecondaryContainer = Color(0xFFB6EAE4),
    tertiary = Color(0xFFE1BF95),
    onTertiary = Color(0xFF4F361B),
    tertiaryContainer = Color(0xFF624729),
    onTertiaryContainer = Color(0xFFF7DDBB),
    background = Color(0xFF101820),
    surface = Color(0xFF17222D),
    surfaceVariant = Color(0xFF213340),
    onSurface = Color(0xFFE9F2F8),
    onSurfaceVariant = Color(0xFFAFC3D0),
    outline = Color(0xFF86A1B0),
    outlineVariant = Color(0xFF334B5A),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    surfaceTint = Color(0xFF9CCFF0),
    inverseSurface = Color(0xFFE2EDF4),
    inverseOnSurface = Color(0xFF1D303D),
    inversePrimary = Color(0xFF1B6797),
)

object GnssSpacing {
    val xs = 4.dp
    val sm = 8.dp
    val md = 12.dp
    val lg = 16.dp
    val xl = 24.dp
    val xxl = 32.dp
    val screen = 20.dp
}

private val AppShapes = Shapes(
    small = RoundedCornerShape(6.dp),
    medium = RoundedCornerShape(10.dp),
    large = RoundedCornerShape(16.dp),
)

private val AppTypography = Typography(
    displaySmall = TextStyle(fontSize = 36.sp, lineHeight = 42.sp, fontWeight = FontWeight.Medium),
    headlineMedium = TextStyle(fontSize = 27.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold),
    headlineSmall = TextStyle(fontSize = 23.sp, lineHeight = 30.sp, fontWeight = FontWeight.Medium),
    titleLarge = TextStyle(fontSize = 20.sp, lineHeight = 27.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, lineHeight = 23.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 21.sp),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 18.sp),
    labelLarge = TextStyle(fontSize = 14.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 12.sp, lineHeight = 17.sp, fontWeight = FontWeight.Medium),
    labelSmall = TextStyle(fontSize = 11.sp, lineHeight = 15.sp, fontWeight = FontWeight.Medium),
)

internal val LocalGnssDark = compositionLocalOf { false }

@Composable
fun GnssTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalGnssDark provides darkTheme) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColors else LightColors,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}
