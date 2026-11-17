from app.test_main import client


def test_gate_demo_fails() -> None:
    assert client.get('/health').status_code == 500

