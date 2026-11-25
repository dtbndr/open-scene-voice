"""Shape validator for the beats sidecar (version 1)."""

import re
from typing import Any

from scenevoice.beats.beats_constants import SIDECAR_VERSION
from scenevoice.beats.check_keys import check_keys
from scenevoice.beats.check_scene_shape import check_scene_shape
from scenevoice.beats.is_plain_int import is_plain_int

_KEYS = ("version", "script_sha256", "scenes")
_HASH = re.compile(r"[0-9a-f]{64}")


def check_sidecar_shape(doc: Any) -> str | None:
    """Return a one-line problem naming the field, or None when `doc` is valid.

    Accepts any object and never raises.
    """
    try:
        return _check(doc)
    except Exception as exc:  # defensive: hostile objects must not escape
        return f"sidecar could not be checked ({type(exc).__name__})"


def _check(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return "sidecar must be an object"
    problem = check_keys("sidecar", doc, _KEYS)
    if problem:
        return problem
    version = doc["version"]
    if not is_plain_int(version) or version != SIDECAR_VERSION:
        return f"version must be the integer {SIDECAR_VERSION}"
    digest = doc["script_sha256"]
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        return "script_sha256 must be 64 lowercase hex characters"
    scenes = doc["scenes"]
    if not isinstance(scenes, list):
        return "scenes must be a list"
    for position, scene in enumerate(scenes, start=1):
        problem = check_scene_shape(position, scene)
        if problem:
            return problem
    return None
