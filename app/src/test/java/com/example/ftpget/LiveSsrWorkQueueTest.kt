package com.example.ftpget

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class LiveSsrWorkQueueTest {
    @Test fun ordinaryStopDrainsEveryAcceptedEvent() {
        val events = mutableListOf<Int>()
        val queue = LiveSsrWorkQueue { error(it) }
        repeat(8) { i -> queue.enqueue { events += i } }
        queue.close()
        assertEquals((0..7).toList(), events)
    }

    @Test fun liveExceptionStopsLaterProcessingAndReportsOnlyOnce() {
        val failures = mutableListOf<String>()
        val work = mutableListOf<Int>()
        val queue = LiveSsrWorkQueue { failures += it }
        queue.enqueue { work += 1 }
        queue.enqueue { error("fixture") }
        queue.enqueue { work += 2 }
        queue.close()
        assertEquals(listOf(1), work)
        assertEquals(listOf("LIVE_RECORD_ERROR"), failures)
    }

    @Test fun overflowDoesNotResumeAcrossMissingReceipt() {
        val entered = CountDownLatch(1)
        val resume = CountDownLatch(1)
        val events = mutableListOf<String>()
        val queue = LiveSsrWorkQueue(1) { events += it }
        try {
            queue.enqueue {
                entered.countDown()
                check(resume.await(5, TimeUnit.SECONDS))
                events += "in-flight epoch"
            }
            assertTrue(entered.await(5,TimeUnit.SECONDS))
            queue.enqueue { events += "queued" }
            queue.enqueue { events += "overflow" }
            queue.enqueue { events += "late" }
        } finally {
            resume.countDown()
            queue.close()
        }
        assertEquals(listOf("in-flight epoch","LIVE_QUEUE_OVERFLOW"), events)
    }
}
