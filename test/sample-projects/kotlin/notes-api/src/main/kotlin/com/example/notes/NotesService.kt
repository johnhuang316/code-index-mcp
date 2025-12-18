package com.example.notes

class NotesService(private val repo: NoteRepository) {

    fun createNote(id: String, body: String): Note {
        val note = Note(id = id, title = id.replaceFirstChar { it.uppercase() }, body = body)
        repo.save(note)
        return note
    }

    fun find(id: String): Note? = repo.find(id)

    fun publish(id: String): Note? {
        val note = repo.find(id) ?: return null
        val published = note.copy(published = true)
        repo.update(published)
        return published
    }
}