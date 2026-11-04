package com.example.ftpget

import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest
import java.nio.file.Files
import java.util.UUID

/** Versioned migration of known bundled products; never overwrite a user ATX.
 * The replacement is an unchanged satellite-block subset of official IGS
 * igs20_2437.atx. It includes the dated histories of reassigned BeiDou PRNs.
 * Unknown user products still require epoch/signal coverage checks in native.
 */
object AntennaProductVersion {
    const val revision = "IGS20_2437_SATELLITE_HISTORY_20261026"
    const val bundledSha256 = "737c46fcfd30b80a8a622f011f88bae779449e6a14781ac6e1a558934004261a"
    private val staleHashes = setOf(
        "fd9955ae17d759291e62e144db8e47a3d4f38bb1d8aae7a8e093fbc6cad0b79f"
    )

    internal fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
    }

    fun isKnownStale(file: File): Boolean = file.isFile && sha256(file) in staleHashes

    /** No stale file is accepted just because its filename/header looks valid. */
    fun usable(file: File): Boolean = file.isFile && file.length() >= 1_000_000L &&
        file.bufferedReader().use { it.readLine()?.contains("ANTEX VERSION / SYST") == true } &&
        !isKnownStale(file)

    internal fun verifyBundled(file: File) {
        if (!usable(file) || sha256(file) != bundledSha256) {
            throw IOException("内置 ANTEX 版本校验失败：$revision")
        }
    }

    /** Only a byte-exact known old bundled file is automatically migrated.
     * The new bytes are fully verified before moving the old file; a backup
     * remains outside the .ATX selection pattern. Failure restores the old
     * path where possible and never discards its backup.
     * Injectable catalog entries make failure/rollback testable without a
     * device, network access or production-sized fixture copies.
     */
    internal fun migrateKnownStale(
        destination: File,
        asset: () -> InputStream,
        status: (String) -> Unit = {},
        knownStale: Set<String> = staleHashes,
        expectedSha256: String = bundledSha256
    ): Boolean {
        if (!destination.isFile || sha256(destination) !in knownStale) return false
        val oldHash = sha256(destination)
        val parent = destination.parentFile ?: throw IOException("ANTEX 目录无效")
        val token = UUID.randomUUID().toString()
        val temporary = File(parent, "${destination.name}.$token.part")
        val backup = File(parent, "${destination.name}.legacy-${oldHash.take(12)}-$token.bak")
        var movedOld = false
        try {
            asset().use { input -> temporary.outputStream().use { input.copyTo(it) } }
            if (sha256(temporary) != expectedSha256) throw IOException("新版 ANTEX 哈希不符，保留原文件")
            // Recheck before the move: do not overwrite a file changed by a user.
            if (sha256(destination) != oldHash) throw IOException("ANTEX 在迁移期间发生变化，停止替换")
            Files.move(destination.toPath(), backup.toPath())
            movedOld = true
            // No REPLACE_EXISTING: a concurrent user's new file must survive.
            Files.move(temporary.toPath(), destination.toPath())
            status("已更新 ANTEX：$revision；原文件保留为 ${backup.name}")
            return true
        } catch (error: Exception) {
            if (movedOld && !destination.exists()) {
                try { Files.move(backup.toPath(), destination.toPath()) }
                catch (restoreError: Exception) {
                    throw IOException("ANTEX 更新失败；原文件仍保留在 ${backup.absolutePath}", error)
                }
            }
            throw error
        } finally {
            if (temporary.exists()) temporary.delete()
        }
    }
}
