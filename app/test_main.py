from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app import main
from app.main import MAX_NOTES, app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_store() -> Iterator[None]:
    reset_store()
    yield
    reset_store()


def _create(title: str = "Alpha", content: str = "First note") -> dict[str, object]:
    response = client.post("/notes", json={"title": title, "content": content})
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_read_note() -> None:
    created = _create()
    assert created == {"id": 1, "title": "Alpha", "content": "First note"}

    fetch_response = client.get("/notes/1")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["title"] == "Alpha"


def test_list_notes_returns_all_created() -> None:
    assert client.get("/notes").json() == []
    _create("A", "a")
    _create("B", "b")
    titles = [n["title"] for n in client.get("/notes").json()]
    assert titles == ["A", "B"]


def test_update_note_partial_fields() -> None:
    _create()
    response = client.put("/notes/1", json={"content": "Changed"})
    assert response.status_code == 200
    assert response.json() == {"id": 1, "title": "Alpha", "content": "Changed"}

    response = client.put("/notes/1", json={"title": "Beta"})
    assert response.json() == {"id": 1, "title": "Beta", "content": "Changed"}


def test_delete_note_then_gone() -> None:
    _create()
    assert client.delete("/notes/1").status_code == 204
    assert client.get("/notes/1").status_code == 404
    assert client.delete("/notes/1").status_code == 404


def test_identifiers_are_not_reused_after_delete() -> None:
    _create()
    client.delete("/notes/1")
    assert _create()["id"] == 2


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_missing_note_returns_404(method: str) -> None:
    kwargs = {"json": {"title": "x"}} if method == "put" else {}
    response = getattr(client, method)("/notes/999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "x"},
        {"title": "   ", "content": "x"},
        {"title": "x", "content": ""},
        {"title": "x" * 201, "content": "x"},
        {"title": "x", "content": "x" * 2001},
        {"title": "x"},
        {"content": "x"},
        {"title": 5, "content": "x"},
        {"title": "x", "content": "x", "admin": True},
        [],
    ],
)
def test_invalid_create_payload_is_rejected(payload: object) -> None:
    response = client.post("/notes", json=payload)
    assert response.status_code == 422
    assert client.get("/notes").json() == []


def test_boundary_lengths_are_accepted() -> None:
    created = _create("x" * 200, "y" * 2000)
    assert len(str(created["title"])) == 200


def test_whitespace_is_stripped() -> None:
    assert _create("  Alpha  ", " body ")["title"] == "Alpha"


@pytest.mark.parametrize(
    "payload",
    [{"title": ""}, {"content": "x" * 2001}, {"unknown": "x"}],
)
def test_invalid_update_payload_is_rejected_and_note_unchanged(payload: object) -> None:
    _create()
    assert client.put("/notes/1", json=payload).status_code == 422
    assert client.get("/notes/1").json()["title"] == "Alpha"


@pytest.mark.parametrize("note_id", ["0", "-1", "abc", "1.5", str(2**31), "99999999999999999999"])
def test_invalid_note_id_is_rejected(note_id: str) -> None:
    assert client.get(f"/notes/{note_id}").status_code == 422


def test_store_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "MAX_NOTES", 2)
    _create()
    _create()
    response = client.post("/notes", json={"title": "x", "content": "x"})
    assert response.status_code == 507
    assert len(client.get("/notes").json()) == 2


def test_default_store_limit_is_bounded() -> None:
    assert 0 < MAX_NOTES <= 10_000


_printable = st.characters(blacklist_categories=("Cc", "Cs"))


@settings(max_examples=100, deadline=None)
@given(
    title=st.text(_printable, min_size=1, max_size=200).filter(lambda s: s.strip() != ""),
    content=st.text(_printable, min_size=1, max_size=2000).filter(lambda s: s.strip() != ""),
)
def test_valid_text_round_trips(title: str, content: str) -> None:
    reset_store()
    created = client.post("/notes", json={"title": title, "content": content}).json()
    fetched = client.get(f"/notes/{created['id']}").json()
    assert fetched == {"id": created["id"], "title": title.strip(), "content": content.strip()}


@pytest.mark.parametrize("char", ["\x00", "\x07", "\x1b", "\x1f", "\x7f", "\x85", "\x9b"])
def test_control_characters_are_rejected(char: str) -> None:
    assert client.post("/notes", json={"title": f"a{char}b", "content": "x"}).status_code == 422
    assert client.post("/notes", json={"title": "x", "content": f"a{char}b"}).status_code == 422


def test_content_allows_tabs_and_line_breaks() -> None:
    assert _create("t", "line1\n\tline2\r\nline3")["content"] == "line1\n\tline2\r\nline3"


@settings(max_examples=100, deadline=None)
@given(payload=st.dictionaries(st.text(max_size=10), st.text(max_size=50), max_size=4))
def test_arbitrary_payloads_never_cause_server_errors(payload: dict[str, str]) -> None:
    response = client.post("/notes", json=payload)
    assert response.status_code in {200, 422}


@pytest.mark.parametrize("path", ["/health", "/notes", "/notes/999", "/does-not-exist"])
def test_security_headers_on_every_response(path: str) -> None:
    response = client.get(path)
    for name, value in main.SECURITY_HEADERS.items():
        assert response.headers[name] == value


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_disabled(path: str) -> None:
    assert client.get(path).status_code == 404
