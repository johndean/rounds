"""
GCS service — signed-URL generation + scope-validation invariant (R7).

The bucket layout is fixed by audit §2.4:

    gs://<bucket>/sessions/<session_id>/<filename>            (role=video)
    gs://<bucket>/sessions/<session_id>/slides/<filename>     (role=slide)
    gs://<bucket>/sessions/<session_id>/manifest/<filename>   (role=manifest)
    gs://<bucket>/sessions/<session_id>/uploads/<filename>    (role=audio_enhance / other)

The `/upload-complete` endpoint MUST reject any client-submitted `gcs_uri`
outside `gs://<bucket>/sessions/<session_id>/`. This is the security boundary
documented in MIC audit §2.7 / `_find_out_of_scope_uri`. Test:
tests/test_gcs_scope.py asserts the rejection path.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable, Optional

from app.config import settings

# Role → subdirectory mapping. Mirrors MIC audit §2.4 + §8 ref `_blob_name_for_role`.
_ROLE_PREFIXES: dict[str, str] = {
    "video":         "",                # session-root: gs://b/sessions/<id>/<filename>
    "slide":         "slides/",
    "manifest":      "manifest/",
    "audio_enhance": "uploads/",
    "audio":         "uploads/",
    "chat":          "chat/",           # raw chat-transcript .txt — manifest parser ingests
    "other":         "uploads/",
}


def session_prefix(session_id: str) -> str:
    """Returns gs://<bucket>/sessions/<session_id>/  (always trailing slash)."""
    return f"gs://{settings.GCS_BUCKET}/sessions/{session_id}/"


def blob_name_for_role(session_id: str, role: Optional[str], filename: str) -> str:
    """
    Compose the GCS object name for a given session/role/filename triple.
    Falls back to the `other` (uploads/) prefix when role is unknown — same
    posture as MIC's `_blob_name_for_role` so a future role addition
    doesn't accidentally land in the bucket root.
    """
    subdir = _ROLE_PREFIXES.get(role or "other", _ROLE_PREFIXES["other"])
    safe_filename = filename.lstrip("/")
    return f"sessions/{session_id}/{subdir}{safe_filename}"


def gcs_uri(session_id: str, role: Optional[str], filename: str) -> str:
    """gs:// URI corresponding to blob_name_for_role()."""
    return f"gs://{settings.GCS_BUCKET}/{blob_name_for_role(session_id, role, filename)}"


def find_out_of_scope_uri(files: Iterable[dict], session_id: str) -> Optional[str]:
    """
    Returns the first `gcs_uri` from `files` that is OUTSIDE the session's
    expected prefix, or None if every uri is in-scope.

    `files` items must carry a `gcs_uri` field; missing fields are tolerated
    (treated as out-of-scope so the caller rejects).
    """
    expected = session_prefix(session_id)
    for f in files:
        uri = f.get("gcs_uri")
        if not isinstance(uri, str) or not uri.startswith(expected):
            return uri if isinstance(uri, str) else "<missing>"
    return None


def make_signed_put_url(session_id: str, role: Optional[str], filename: str, ttl_minutes: int = 60) -> tuple[str, str]:
    """
    Return (signed_url, gcs_uri) for an upload PUT.
    Lazy-imports google.cloud.storage so unit tests that don't touch GCS
    don't pay the SDK import cost / credential check.
    """
    from google.cloud import storage as gcs_lib  # type: ignore

    client = gcs_lib.Client(project=settings.GCP_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET)
    blob_name = blob_name_for_role(session_id, role, filename)
    blob = bucket.blob(blob_name)
    signed_url = blob.generate_signed_url(
        version="v4",
        method="PUT",
        expiration=timedelta(minutes=ttl_minutes),
    )
    return signed_url, f"gs://{settings.GCS_BUCKET}/{blob_name}"
