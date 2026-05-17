"""
R7 invariant: /v1/gcs/upload-complete rejects any gcs_uri outside the
session's expected `gs://<bucket>/sessions/<id>/` prefix.

Mirrors MIC audit §2.7 / `_find_out_of_scope_uri`.
"""
from importlib import reload

from fastapi.testclient import TestClient

import pytest


def _authed_client(monkeypatch):
    """Configure AUTH_USERS + GCS_BUCKET + reload modules, return a logged-in client."""
    monkeypatch.setenv("AUTH_USERS", "tester@vin.com:supersecret")
    monkeypatch.setenv("GCS_BUCKET", "rounds-test-bucket")
    from app import auth as auth_mod, config as config_mod, main
    reload(config_mod)
    reload(auth_mod)
    reload(main)
    client = TestClient(main.app)
    resp = client.post("/v1/auth/login", data={"username": "tester@vin.com", "password": "supersecret"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_in_scope_uri_accepted(monkeypatch):
    client = _authed_client(monkeypatch)
    resp = client.post(
        "/v1/gcs/upload-complete",
        json={
            "session_id": "abc-123",
            "files": [
                {"gcs_uri": "gs://rounds-test-bucket/sessions/abc-123/video.mp4", "role": "video"},
                {"gcs_uri": "gs://rounds-test-bucket/sessions/abc-123/slides/01.png", "role": "slide"},
                {"gcs_uri": "gs://rounds-test-bucket/sessions/abc-123/manifest/extras.json", "role": "manifest"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "abc-123"
    assert len(body["accepted"]) == 3


@pytest.mark.parametrize("offending_uri,reason", [
    ("gs://rounds-test-bucket/sessions/OTHER-SESSION/video.mp4",  "cross-session"),
    ("gs://rounds-test-bucket/other-prefix/sneaky.mp4",            "wrong-prefix"),
    ("gs://different-bucket/sessions/abc-123/video.mp4",           "wrong-bucket"),
    ("http://evil.example.com/file.mp4",                            "non-gcs scheme"),
    ("",                                                             "empty uri"),
])
def test_out_of_scope_uri_rejected(monkeypatch, offending_uri, reason):
    client = _authed_client(monkeypatch)
    resp = client.post(
        "/v1/gcs/upload-complete",
        json={
            "session_id": "abc-123",
            "files": [
                {"gcs_uri": "gs://rounds-test-bucket/sessions/abc-123/video.mp4"},
                {"gcs_uri": offending_uri},
            ],
        },
    )
    # Pydantic rejects "" before our validator (min_length=1) → 422.
    # Everything else hits our handler → 400 VALIDATION_FAILED.
    if offending_uri == "":
        assert resp.status_code == 422, f"{reason}: expected pydantic 422, got {resp.status_code} {resp.text}"
    else:
        assert resp.status_code == 400, f"{reason}: expected 400, got {resp.status_code} {resp.text}"
        body = resp.json()
        assert body["detail"]["code"] == "VALIDATION_FAILED"
        assert body["detail"]["offending_uri"] == offending_uri


def test_upload_complete_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "tester@vin.com:supersecret")
    monkeypatch.setenv("GCS_BUCKET", "rounds-test-bucket")
    from app import auth as auth_mod, config as config_mod, main
    reload(config_mod)
    reload(auth_mod)
    reload(main)
    client = TestClient(main.app)
    resp = client.post(
        "/v1/gcs/upload-complete",
        json={"session_id": "x", "files": [{"gcs_uri": "gs://rounds-test-bucket/sessions/x/v.mp4"}]},
    )
    assert resp.status_code == 401


def test_blob_name_for_role_layout(monkeypatch):
    """Bucket layout from audit §2.4 must be exact."""
    monkeypatch.setenv("GCS_BUCKET", "rounds-test-bucket")
    from app import config as config_mod
    reload(config_mod)
    from app.services import gcs as gcs_svc
    reload(gcs_svc)

    assert gcs_svc.blob_name_for_role("S1", "video", "lecture.mp4")    == "sessions/S1/lecture.mp4"
    assert gcs_svc.blob_name_for_role("S1", "slide", "01.png")          == "sessions/S1/slides/01.png"
    assert gcs_svc.blob_name_for_role("S1", "manifest", "extras.json")  == "sessions/S1/manifest/extras.json"
    assert gcs_svc.blob_name_for_role("S1", "audio_enhance", "fix.mp3") == "sessions/S1/uploads/fix.mp3"
    # Unknown role falls back to uploads/
    assert gcs_svc.blob_name_for_role("S1", "other", "f.bin")           == "sessions/S1/uploads/f.bin"
    assert gcs_svc.blob_name_for_role("S1", None, "f.bin")              == "sessions/S1/uploads/f.bin"


def test_session_prefix_format(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET", "rounds-test-bucket")
    from app import config as config_mod
    reload(config_mod)
    from app.services import gcs as gcs_svc
    reload(gcs_svc)
    assert gcs_svc.session_prefix("abc-123") == "gs://rounds-test-bucket/sessions/abc-123/"
