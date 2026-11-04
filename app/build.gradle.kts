import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
}

// Some IDE/test launchers request the Java plugin's task name. Android exposes
// variant-specific tasks instead. Compile the actual Debug unit-test sources;
// this alias does not execute tests (use :app:testDebugUnitTest for that).
tasks.register("testClasses") {
    group = "build"
    description = "Compiles Debug unit-test classes (Android compatibility alias)."
    dependsOn("compileDebugUnitTestSources")
}

// 本地凭据文件被 Git 忽略；新机器可以从 example 复制后填写，不能提交真实密码。
// 缺少配置时仍可编译，沿用界面现有的“跳过 VMF3 下载”提示。
val vmf3LocalProperties = Properties().apply {
    val credentialsFile = rootProject.file("vmf3.local.properties")
    if (credentialsFile.isFile) credentialsFile.inputStream().use { load(it) }
}

// Personal debug APK only: local defaults are ignored by Git and never logged.
val ntripLocalProperties = Properties().apply {
    val credentialsFile = rootProject.file("ntrip.local.properties")
    if (credentialsFile.isFile) credentialsFile.inputStream().use { load(it) }
}

// BuildConfig 字段要求 Java 字符串字面量，转义防止引号/反斜杠等破坏生成代码。
fun vmf3JavaString(value: String): String = "\"" + value
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
    .replace("\r", "\\r")
    .replace("\n", "\\n")
    .replace("\t", "\\t") + "\""

android {
    namespace = "com.example.ftpget"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.pppntrip"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("String", "VMF3_USERNAME",
            vmf3JavaString(vmf3LocalProperties.getProperty("vmf3.username", "")))
        buildConfigField("String", "VMF3_PASSWORD",
            vmf3JavaString(vmf3LocalProperties.getProperty("vmf3.password", "")))

    }
    buildFeatures {
        buildConfig = true
        compose = true
    }
    externalNativeBuild {
        cmake {
            path ("src/main/cpp/CMakeLists.txt")

        }
    }
    buildTypes {
        debug {
            buildConfigField("String", "NTRIP_DEFAULT_USER",
                vmf3JavaString(ntripLocalProperties.getProperty("ntrip.username", "")))
            buildConfigField("String", "NTRIP_DEFAULT_PASSWORD",
                vmf3JavaString(ntripLocalProperties.getProperty("ntrip.password", "")))
        }
        release {
            buildConfigField("String", "NTRIP_DEFAULT_USER", "\"\"")
            buildConfigField("String", "NTRIP_DEFAULT_PASSWORD", "\"\"")
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation("commons-net:commons-net:3.9.0")
    // Kotlin 协程库
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1")
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.constraintlayout)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.activity.compose)
    debugImplementation(libs.androidx.compose.ui.tooling)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
