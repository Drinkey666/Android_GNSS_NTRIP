package com.example.ftpget

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest
import java.time.LocalDateTime
import java.time.ZoneOffset

class AntennaProductVersionTest {
    @get:Rule val temporary = TemporaryFolder()
    private val old = "old known bundled product".toByteArray()
    private val current = "verified new official product".toByteArray()
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun destination() = temporary.newFile("igs20.atx").apply { writeBytes(old) }

    @Test fun knownOldProductIsBackedUpBeforeInstallingVerifiedBytes() {
        val file = destination()
        assertTrue(AntennaProductVersion.migrateKnownStale(file,
            { ByteArrayInputStream(current) }, knownStale = setOf(hash(old)), expectedSha256 = hash(current)))
        assertArrayEquals(current, file.readBytes())
        val backups = temporary.root.listFiles()!!.filter { it.name.endsWith(".bak") }
        assertEquals(1, backups.size)
        assertArrayEquals(old, backups.single().readBytes())
        assertFalse(backups.single().name.endsWith(".ATX", ignoreCase = true))
    }

    @Test fun unknownUserProductIsNotReplacedAndAssetIsNotOpened() {
        val file = destination().apply { writeText("user supplied independent product") }
        val before = file.readBytes()
        assertFalse(AntennaProductVersion.migrateKnownStale(file,
            { fail("Must not open asset for an unknown user product"); ByteArrayInputStream(current) },
            knownStale = setOf(hash(old)), expectedSha256 = hash(current)))
        assertArrayEquals(before, file.readBytes())
    }

    @Test fun successfulMigrationIsIdempotentWithoutAnotherBackup() {
        val file = destination()
        AntennaProductVersion.migrateKnownStale(file, { ByteArrayInputStream(current) },
            knownStale = setOf(hash(old)), expectedSha256 = hash(current))
        assertFalse(AntennaProductVersion.migrateKnownStale(file,
            { fail("Updated product must not be recopied"); ByteArrayInputStream(current) },
            knownStale = setOf(hash(old)), expectedSha256 = hash(current)))
        assertArrayEquals(current, file.readBytes())
        assertEquals(2, temporary.root.listFiles()!!.size)
    }

    @Test fun corruptReplacementLeavesOriginalAtItsPath() {
        val file = destination()
        assertThrows(IOException::class.java) {
            AntennaProductVersion.migrateKnownStale(file,
                { ByteArrayInputStream("corrupt".toByteArray()) },
                knownStale = setOf(hash(old)), expectedSha256 = hash(current))
        }
        assertArrayEquals(old, file.readBytes())
        assertEquals(1, temporary.root.listFiles()!!.size)
    }

    @Test fun interruptedAssetReadDoesNotMoveOrEraseOldProduct() {
        val file = destination()
        assertThrows(IOException::class.java) {
            AntennaProductVersion.migrateKnownStale(file, {
                object : InputStream() { override fun read(): Int = throw IOException("read interrupted") }
            }, knownStale = setOf(hash(old)), expectedSha256 = hash(current))
        }
        assertArrayEquals(old, file.readBytes())
        assertEquals(1, temporary.root.listFiles()!!.size)
    }

    @Test fun userChangeDuringCopyIsPreserved() {
        val file = destination()
        assertThrows(IOException::class.java) {
            AntennaProductVersion.migrateKnownStale(file, {
                file.writeText("user changed this product during copy")
                ByteArrayInputStream(current)
            }, knownStale = setOf(hash(old)), expectedSha256 = hash(current))
        }
        assertEquals("user changed this product during copy", file.readText())
        assertEquals(1, temporary.root.listFiles()!!.size)
    }

    @Test fun packagedBytesMatchVerifiedOfficialCatalogAndHistoricalIdentities() {
        val file = File("src/main/assets/gnss_products/igs20.atx")
        assertTrue(file.isFile)
        assertEquals(AntennaProductVersion.bundledSha256, AntennaProductVersion.sha256(file))
        AntennaProductVersion.verifyBundled(file)
        fun identities(whenUtc: LocalDateTime): Map<String, String> {
            val t = whenUtc.toEpochSecond(ZoneOffset.UTC)
            val result = mutableMapOf<String, String>()
            var prn = ""; var svn = ""; var start = Long.MIN_VALUE; var end = Long.MAX_VALUE
            fun epoch(s: String): Long {
                val q = s.trim().split(Regex("\\s+"))
                return LocalDateTime.of(q[0].toInt(), q[1].toInt(), q[2].toInt(),
                    q[3].toInt(), q[4].toInt(), q[5].toDouble().toInt()).toEpochSecond(ZoneOffset.UTC)
            }
            file.forEachLine { line ->
                when (line.drop(60).trim()) {
                    "START OF ANTENNA" -> { prn = ""; svn = ""; start = Long.MIN_VALUE; end = Long.MAX_VALUE }
                    "TYPE / SERIAL NO" -> { prn = line.substring(20, 40).trim(); svn = line.substring(40, 50).trim() }
                    "VALID FROM" -> start = epoch(line.take(60))
                    "VALID UNTIL" -> end = epoch(line.take(60))
                    "END OF ANTENNA" -> if (prn in setOf("C06", "C07", "C08", "C12") && t in start..end) {
                        assertFalse("Ambiguous identity for $prn", prn in result)
                        result[prn] = svn
                    }
                }
            }
            return result
        }
        assertEquals(mapOf("C06" to "C220", "C07" to "C221", "C08" to "C224", "C12" to "C233"),
            identities(LocalDateTime.of(2026, 10, 25, 6, 10)))
        assertEquals(mapOf("C06" to "C005", "C07" to "C007", "C08" to "C008", "C12" to "C013"),
            identities(LocalDateTime.of(2026, 3, 17, 5, 33)))
    }

    @Test fun legacyBackupCannotWinTheAntennaFileSelector() {
        val header = "     1.4            M       ANTEX VERSION / SYST\n"
        val valid = temporary.newFile("igs20.atx").apply { writeText(header + "\n".repeat(1_000_000)) }
        temporary.newFile("igs20.atx.legacy-old.bak").apply { writeText(header + "\n".repeat(1_000_000)); setLastModified(System.currentTimeMillis() + 60_000) }
        assertEquals(valid.canonicalPath, LivePppProducts.resolveAntennaFile(temporary.root).canonicalPath)
    }
}
