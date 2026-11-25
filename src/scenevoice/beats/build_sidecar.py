"""Build the canonical beats sidecar document (WS35 decision 7)."""

from typing import Any

from scenevoice.beats.beats_constants import SIDECAR_VERSION
from scenevoice.beats.hash_script_bytes import hash_script_bytes
from scenevoice.validation.scene import Scene


def build_sidecar(
    script_bytes: bytes,
    scenes: list[Scene],
    segment_counts: list[int],
    parsed: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the sidecar for a reply that already passed `check_beats_coverage`.

    `ordinal`, `title` and `segment_count` come from the script (position,
    Scene and counts), never from the reply; only beat ranges and notes are
    taken from `parsed`, which is not modified. Notes lose surrounding
    whitespace. Key order is fixed by construction.
    """
    sidecar_scenes: list[dict[str, Any]] = []
    for position, (scene, count, reply_scene) in enumerate(zip(scenes, segment_counts, parsed, strict=True), start=1):
        beats = [
            {"first": beat["first"], "last": beat["last"], "note": beat["note"].strip()}
            for beat in reply_scene["beats"]
        ]
        sidecar_scenes.append(
            {"ordinal": position, "title": scene.title, "segment_count": count, "beats": beats}
        )
    return {
        "version": SIDECAR_VERSION,
        "script_sha256": hash_script_bytes(script_bytes),
        "scenes": sidecar_scenes,
    }
