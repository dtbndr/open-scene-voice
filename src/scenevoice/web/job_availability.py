from collections.abc import Mapping

from .check_rest_ready import MISMATCH, NOTHING_VOICED, check_rest_ready
from .common_settings import common_settings
from .project_facts import ProjectFacts

SAVE_FIRST = "Save a script first."
FIX_FIRST = "Fix the problems in your script first."
STARTED = "Voicing has already started for this project. Choose Voice the rest or Start again."
SETTINGS_DIFFER = "One script uses one voice and model. These settings differ from the ones already used."
BEATS_EXIST = "Beats already exist. Choose Redo beats."
NO_BEATS = "There are no beats yet."
VOICE_EVERY = "Voice every scene before this step."
ALL_VOICED = "Every scene is already voiced."  # not in the J12 list: the one string chosen here for rest with nothing left

KINDS = {"synth": ("all", "rest", "restart"), "synth-scene": (None,), "align": (None,), "beats": (None,), "beats-redo": (None,), "pack": (None,)}


def _differs(facts: ProjectFacts, requested: Mapping[str, str | None]) -> bool:
    recorded = common_settings(facts.record.items) or {}
    return any(recorded.get(name) != value for name, value in requested.items())


def _every_scene_voiced(facts: ProjectFacts) -> bool:
    return all(scene.ordinal in facts.audio.hashes for scene in facts.scenes)


def _scene(facts: ProjectFacts, requested: Mapping[str, str | None]) -> str | None:
    """synth-scene: needs the `audio/` folder (the CLI refuses without it) and the record-settings rule (J3); the seven rest refusals are scoped to `rest`."""
    if not facts.audio.folder or (not facts.record.items and not facts.audio.hashes):
        return NOTHING_VOICED
    if facts.record.state != "ok" or common_settings(facts.record.items) is None:
        return MISMATCH
    return SETTINGS_DIFFER if _differs(facts, requested) else None


def _voicing(facts: ProjectFacts, kind: str, mode: str | None, requested: Mapping[str, str | None]) -> str | None:
    if kind == "synth" and mode == "all":
        return STARTED if facts.audio.named else None
    if kind == "synth" and mode == "restart":
        return None
    if kind == "synth-scene":
        return _scene(facts, requested)
    refusal = check_rest_ready(facts.scenes, facts.audio, facts.record, facts.timings)
    if refusal is not None:
        return refusal
    if _every_scene_voiced(facts):
        return ALL_VOICED
    return SETTINGS_DIFFER if _differs(facts, requested) else None


def job_availability(
    facts: ProjectFacts, kind: str, mode: str | None = None, requested: Mapping[str, str | None] | None = None
) -> str | None:
    """None when the job may start, else its J12 not_allowed message: the ONE place that decides, from disk facts.

    `requested` holds the client-supplied settings (`voice`, `model`, `language`, `instruction`) for the rest and
    single-scene kinds; a value that differs from the recorded common settings is refused. The detail route's `can`
    flags and the start route both call this, so flags and refusals cannot drift.
    """
    if kind not in KINDS or mode not in KINDS[kind]:
        raise ValueError(f"unknown job kind or mode: {kind} {mode}")
    if facts.script == "none":
        return SAVE_FIRST
    if facts.script != "ok":
        return FIX_FIRST
    if kind in ("synth", "synth-scene"):
        return _voicing(facts, kind, mode, requested or {})
    if kind in ("align", "pack"):
        return None if _every_scene_voiced(facts) else VOICE_EVERY
    exists = facts.beats != "none"
    if kind == "beats":
        return BEATS_EXIST if exists else None
    return None if exists else NO_BEATS
