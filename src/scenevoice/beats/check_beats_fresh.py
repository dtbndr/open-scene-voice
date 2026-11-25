"""Freshness check for a beats sidecar against the current script bytes."""

from typing import Any

from scenevoice.beats.check_sidecar_shape import check_sidecar_shape
from scenevoice.beats.hash_script_bytes import hash_script_bytes


def check_beats_fresh(script_bytes: bytes, sidecar: Any) -> str | None:
    """Return a one-line reason the sidecar is unusable, or None when fresh.

    Checks the shape first, then that `script_sha256` matches the bytes.
    Accepts any object as `sidecar` and never raises.
    """
    try:
        problem = check_sidecar_shape(sidecar)
        if problem is not None:
            return problem
        if sidecar["script_sha256"] != hash_script_bytes(script_bytes):
            return "script has changed since the beats sidecar was made"
        return None
    except Exception as exc:  # defensive: never raise to callers
        return f"beats sidecar could not be checked ({type(exc).__name__})"
