package com.example.notes

class NotesApp {
    private val service = NotesService(InMemoryNoteRepository())

    fun run() {
        service.createNote("welcome", "Hello Kotlin")
        service.publish("welcome")
        service.find("welcome")?.let { println("Published: ${'$'}{it.title}") }
    }
}