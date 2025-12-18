package com.example.notes

interface NoteRepository {
    fun save(note: Note)
    fun find(id: String): Note?
    fun update(note: Note)
}

class InMemoryNoteRepository : NoteRepository {
    private val store = mutableMapOf<String, Note>()

    override fun save(note: Note) {
        store[note.id] = note
    }

    override fun find(id: String): Note? = store[id]

    override fun update(note: Note) {
        store[note.id] = note
    }
}