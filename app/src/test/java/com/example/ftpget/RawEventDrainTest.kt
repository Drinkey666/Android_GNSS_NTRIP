package com.example.ftpget

import org.junit.Assert.*
import org.junit.Test
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

class RawEventDrainTest {
    @Test fun stopWaitsForCompleteEpochAndRejectsLaterCallbacks() {
        val gate=RawEventDrain();gate.open()
        val rows=Collections.synchronizedList(mutableListOf<String>())
        val entered=CountDownLatch(1);val finishEvent=CountDownLatch(1);val stopStarted=CountDownLatch(1)
        val closed=AtomicBoolean(false)
        val producer=thread {
            gate.accept {rows+="first";entered.countDown();check(finishEvent.await(5,TimeUnit.SECONDS));rows+="last"}
        }
        assertTrue(entered.await(2,TimeUnit.SECONDS))
        val stopper=thread {stopStarted.countDown();gate.closeAndDrain {rows+="END";closed.set(true)}}
        assertTrue(stopStarted.await(2,TimeUnit.SECONDS));assertFalse(closed.get())
        finishEvent.countDown();producer.join(3000);stopper.join(3000)
        assertFalse(producer.isAlive);assertFalse(stopper.isAlive)
        assertEquals(listOf("first","last","END"),rows)
        assertFalse(gate.accept {rows+="unexpected"});assertEquals(3,rows.size)
    }
    @Test fun failedCallbackDoesNotPreventQueueFinalization() {
        val gate=RawEventDrain();gate.open()
        assertTrue(runCatching {gate.accept {error("TEST_CALLBACK_FAILURE")}}.isFailure)
        var closed=false;gate.closeAndDrain {closed=true}
        assertTrue(closed);assertFalse(gate.isOpen)
    }
}
