package com.example.ftpget

/** Stop cannot close the Raw queue until the last admitted event has enqueued all rows.
 * A callback arriving after close is ignored as a whole, never as a partial epoch.
 */
internal class RawEventDrain {
    private val monitor=Any()
    @Volatile var isOpen=false;private set
    fun open()=synchronized(monitor) {check(!isOpen);isOpen=true}
    fun accept(event:()->Unit):Boolean=synchronized(monitor) {
        if(!isOpen)return@synchronized false
        event();true
    }
    fun closeAndDrain(closeQueue:()->Unit)=synchronized(monitor) {
        isOpen=false
        closeQueue()
    }
}
