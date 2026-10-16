from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_cors_allows_production_origin() -> None:
    response = client.options(
        "/api/live/upload",
        headers={"Origin": "https://soheilon21-a11y.github.io", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "https://soheilon21-a11y.github.io"


def test_cors_rejects_unknown_origin() -> None:
    response = client.options(
        "/api/live/upload",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_localhost_regex_intact() -> None:
    response = client.options(
        "/api/live/upload",
        headers={"Origin": "http://localhost:4321", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:4321"
