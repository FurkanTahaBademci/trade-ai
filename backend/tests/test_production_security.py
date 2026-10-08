"""Production HTTP sinirlari icin regresyon testleri."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_configured_cors_origin_is_allowed():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_cors_origin_is_not_allowed():
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_unknown_host_is_rejected():
    response = client.get("/health", headers={"Host": "evil.example"})
    assert response.status_code == 400
