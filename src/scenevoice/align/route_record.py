import hashlib
from pathlib import Path

from scenevoice.align.record_routing import RecordRouting
from scenevoice.align.record_scene import record_scene
from scenevoice.align.scene_timings import SceneTimings
from scenevoice.synth import (
    ELEVENLABS,
    RECORD_NAME,
    PlanScene,
    SceneWav,
    check_record_path,
    load_record,
    provider_for_model,
)
from scenevoice.validation import Violation


def _rerun(ordinal: int, cause: str) -> str:
    return f"{RECORD_NAME} {cause} for scene {ordinal}, re-run synth --scene {ordinal}"


def route_record(
    scenes: list[PlanScene], wavs: list[SceneWav], directory: str | Path
) -> RecordRouting | str:
    """Check 5a: route each scene to the record or to transcription; a one-line FAIL text on failure.

    Offline and silent: NOTEs are flags in the result. Scenes and wavs are in plan order.
    """
    problem = check_record_path(directory)
    if problem is not None:
        return problem.message
    record = load_record(Path(directory))
    if record is None:
        return RecordRouting((None,) * len(scenes), (), True)
    if isinstance(record, Violation):
        return f"{RECORD_NAME} is not a valid synth record"
    entries = {
        entry.ordinal: entry
        for entry in record
        if entry.ordinal in {s.ordinal for s in scenes}
    }
    elevenlabs = any(
        provider_for_model(e.model) is ELEVENLABS for e in entries.values()
    )
    if not elevenlabs:
        return RecordRouting((None,) * len(scenes), (), False)
    routes: list[SceneTimings | None] = []
    mismatched: list[int] = []
    for scene, wav in zip(scenes, wavs, strict=True):
        entry = entries.get(scene.ordinal)
        if entry is None:
            return _rerun(scene.ordinal, "has no entry")
        if (
            entry.alignment is None
        ):  # Gemini-model entry (D11: null only for Gemini): outcome (d)
            routes.append(None)
            continue
        sha256 = hashlib.sha256(wav.data).hexdigest()
        if entry.sha256 != sha256:
            return _rerun(scene.ordinal, "sha256 differs from the WAV")
        if "".join(entry.alignment.characters) != scene.body:
            routes.append(None)
            mismatched.append(scene.ordinal)
            continue
        timings = record_scene(scene, sha256, entry.alignment)
        if isinstance(timings, str):
            return f"{RECORD_NAME} scene {scene.ordinal}: {timings}"
        routes.append(timings)
    return RecordRouting(tuple(routes), tuple(mismatched), False)
