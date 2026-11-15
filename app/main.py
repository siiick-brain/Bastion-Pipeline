"""Notes service: a small FastAPI app used as the payload for the delivery pipeline."""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_NOTES = 1000
"""Upper bound on stored notes so the in-memory store cannot grow without limit."""

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
}

app = FastAPI(title="Notes service", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


# Control characters (C0, DEL and C1) are rejected. Content may contain tab and line breaks.
_TITLE_CHARS = r"^[^\x00-\x1f\x7f-\x9f]*$"
_CONTENT_CHARS = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]*$"

TitleText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=_TITLE_CHARS),
]
ContentText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, pattern=_CONTENT_CHARS),
]
NoteId = Annotated[int, Path(ge=1, le=2**31 - 1)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoteCreate(_StrictModel):
    title: TitleText
    content: ContentText


class NoteUpdate(_StrictModel):
    title: TitleText | None = None
    content: ContentText | None = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str


notes: dict[int, NoteResponse] = {}
_next_id = 1
_lock = threading.Lock()


def reset_store() -> None:
    """Clear all notes and restart identifiers. Used by tests."""
    global _next_id
    with _lock:
        notes.clear()
        _next_id = 1


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/notes", response_model=list[NoteResponse])
def list_notes() -> list[NoteResponse]:
    with _lock:
        return list(notes.values())


@app.post("/notes", response_model=NoteResponse)
def create_note(note: NoteCreate) -> NoteResponse:
    global _next_id
    with _lock:
        if len(notes) >= MAX_NOTES:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Note limit reached"
            )
        created = NoteResponse(id=_next_id, title=note.title, content=note.content)
        notes[_next_id] = created
        _next_id += 1
        return created


@app.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: NoteId) -> NoteResponse:
    with _lock:
        note = notes.get(note_id)
    if note is None:
        raise _not_found()
    return note


@app.put("/notes/{note_id}", response_model=NoteResponse)
def update_note(note_id: NoteId, note: NoteUpdate) -> NoteResponse:
    with _lock:
        current = notes.get(note_id)
        if current is None:
            raise _not_found()
        updated = current.model_copy(
            update={
                "title": note.title if note.title is not None else current.title,
                "content": note.content if note.content is not None else current.content,
            }
        )
        notes[note_id] = updated
        return updated


@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: NoteId) -> Response:
    with _lock:
        if notes.pop(note_id, None) is None:
            raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
