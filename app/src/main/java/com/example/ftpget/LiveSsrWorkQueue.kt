package com.example.ftpget

import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** A missing receipt invalidates the live solver's prefix. Raw and RTCM writers
 * remain owned by the capture service and can continue to the normal stop. */
internal class LiveSsrWorkQueue(capacity: Int = 512, onFailure: (String) -> Unit) {
    private val failure = AtomicReference<String?>()
    private val executor = object : ThreadPoolExecutor(
        1, 1, 0L, TimeUnit.SECONDS, ArrayBlockingQueue<Runnable>(capacity)
    ) {
        // The final status follows any in-flight epoch's last UI update.
        override fun terminated() { failure.get()?.let(onFailure) }
    }

    fun enqueue(work: () -> Unit) {
        if (executor.isShutdown) return
        try {
            executor.execute {
                if (failure.get() == null) {
                    try { work() } catch (_: Exception) { fail("LIVE_RECORD_ERROR") }
                }
            }
        } catch (_: RejectedExecutionException) {
            if (!executor.isShutdown) fail("LIVE_QUEUE_OVERFLOW")
        }
    }

    private fun fail(reason: String) {
        if (failure.compareAndSet(null, reason)) executor.shutdown()
    }

    fun close() {
        executor.shutdown()
        check(executor.awaitTermination(30, TimeUnit.SECONDS)) { "LIVE_WORKER_NOT_DRAINED" }
    }
}
