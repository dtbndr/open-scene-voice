"""Beats sidecar: constants, shape validator, freshness check and the `run_beats` orchestration."""

from scenevoice.beats.beats_constants import (
    BEATS_MAX_TOKENS,
    MAX_NOTE_CHARS,
    MAX_SCRIPT_CHARS,
    SCRIPT_TOO_LONG_MESSAGE,
    SIDECAR_VERSION,
)
from scenevoice.beats.check_beats_fresh import check_beats_fresh
from scenevoice.beats.check_sidecar_shape import check_sidecar_shape
from scenevoice.beats.hash_script_bytes import hash_script_bytes
from scenevoice.beats.run_beats import run_beats

__all__ = [
    "BEATS_MAX_TOKENS",
    "MAX_NOTE_CHARS",
    "MAX_SCRIPT_CHARS",
    "SCRIPT_TOO_LONG_MESSAGE",
    "SIDECAR_VERSION",
    "check_beats_fresh",
    "check_sidecar_shape",
    "hash_script_bytes",
    "run_beats",
]
