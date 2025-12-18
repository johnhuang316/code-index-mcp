package com.example.notes

data class Note(val id: String, val title: String, val body: String, val published: Boolean = false)

data class CreateNoteRequest(val id: String, val title: String, val body: String)