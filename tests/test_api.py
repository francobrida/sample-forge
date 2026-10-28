import time

import pytest
from fakes import FakeEleven
from fastapi.testclient import TestClient

from sample_forge.api import create_app
from sample_forge.core import Forge


@pytest.fixture
def forge(tmp_path):
    return Forge(FakeEleven(), data_dir=tmp_path, budget=1000)


def wait(c, jid):
    for _ in range(50):
        job = c.get(f"/api/jobs/{jid}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.1)
    raise AssertionError("el job no terminó")


def test_auth_required_when_key_set(forge, monkeypatch):
    monkeypatch.setenv("SF_API_KEY", "secret")
    with TestClient(create_app(forge)) as c:
        assert c.get("/api/budget").status_code == 401
        assert c.get("/api/budget", headers={"x-api-key": "nope"}).status_code == 401
        assert c.get("/api/budget", headers={"x-api-key": "secret"}).status_code == 200


def test_full_flow(forge):
    with TestClient(create_app(forge)) as c:
        body = {"kind": "sfx", "prompt": "glass break", "duration": 1.0}
        assert c.post("/api/estimate", json=body).json()["credits"] == 20
        job = wait(c, c.post("/api/jobs", json=body).json()["id"])
        assert job["status"] == "done", job
        sid = job["results"][0]["id"]
        assert c.get("/api/samples?q=glass").json()[0]["id"] == sid
        assert c.get(f"/api/samples/{sid}/audio").headers["content-type"] == "audio/wav"
        assert c.get(f"/api/export.zip?ids={sid}").content[:2] == b"PK"


def test_input_validation_and_path_safety(forge):
    with TestClient(create_app(forge)) as c:
        assert c.post("/api/jobs", json={"kind": "sfx", "prompt": ""}).status_code == 422
        assert c.get("/api/samples/../../etc/passwd/audio").status_code == 404
        assert c.get("/api/samples/zzzzzzzzzzzz/audio").status_code == 404
        assert c.get("/api/samples?note=H9").status_code == 422
        assert c.get("/api/export.zip?ids=../x").status_code == 400
        assert c.get("/api/jobs/nope").status_code == 404


def test_budget_rejected_at_the_door(forge):
    with TestClient(create_app(forge)) as c:
        big = {"kind": "sfx", "prompt": "boom", "duration": 30, "n": 8}       # 4800 > 1000
        assert c.post("/api/jobs", json=big).status_code == 402
