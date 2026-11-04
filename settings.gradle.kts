pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        // Google-hosted Maven Central mirror; the direct endpoint returns 403
        // on the current network. Keep dependency coordinates/versions intact.
        mavenCentral {
            url = uri("https://maven-central.storage-download.googleapis.com/maven2/")
        }
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral {
            url = uri("https://maven-central.storage-download.googleapis.com/maven2/")
        }
    }
}

rootProject.name = "PPP_NTRIP"
include(":app")
 
