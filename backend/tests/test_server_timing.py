"""API yanıtları web'in yük ölçümü için Server-Timing süresi taşır."""

import re

from fastapi.testclient import TestClient

from app.main import app


def test_responses_carry_server_timing_duration():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert re.fullmatch(r"app;dur=\d+\.\d", response.headers["server-timing"])


def test_rejected_host_still_reports_timing():
    response = TestClient(app).get("/", headers={"host": "evil.invalid"})
    assert response.status_code == 400
    assert response.headers["server-timing"].startswith("app;dur=")
