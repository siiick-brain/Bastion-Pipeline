from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints

app = FastAPI(title='Notes service')

TitleText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
ContentText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class NoteCreate(BaseModel):
    title: TitleText
    content: ContentText


class NoteUpdate(BaseModel):
    title: TitleText | None = None
    content: ContentText | None = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str


notes: dict[int, NoteResponse] = {}
_next_id = 1


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/notes', response_model=list[NoteResponse])
def list_notes() -> list[NoteResponse]:
    return list(notes.values())


@app.post('/notes', response_model=NoteResponse)
def create_note(note: NoteCreate) -> NoteResponse:
    global _next_id

    created = NoteResponse(id=_next_id, title=note.title, content=note.content)
    notes[_next_id] = created
    _next_id += 1
    return created


@app.get('/notes/{note_id}', response_model=NoteResponse)
def get_note(note_id: int) -> NoteResponse:
    note = notes.get(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Note not found')
    return note


@app.put('/notes/{note_id}', response_model=NoteResponse)
def update_note(note_id: int, note: NoteUpdate) -> NoteResponse:
    current = notes.get(note_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Note not found')

    if note.title is not None:
        current.title = note.title
    if note.content is not None:
        current.content = note.content
    notes[note_id] = current
    return current


@app.delete('/notes/{note_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int) -> Response:
    if note_id not in notes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Note not found')
    del notes[note_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
