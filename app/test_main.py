from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_create_and_read_note() -> None:
    payload = {'title': 'Alpha', 'content': 'First note'}

    create_response = client.post('/notes', json=payload)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created['title'] == 'Alpha'
    assert created['content'] == 'First note'

    note_id = created['id']
    fetch_response = client.get(f'/notes/{note_id}')
    assert fetch_response.status_code == 200
    assert fetch_response.json()['title'] == 'Alpha'


def test_invalid_note_payload_is_rejected() -> None:
    response = client.post('/notes', json={'title': '', 'content': 'x'})
    assert response.status_code == 422
