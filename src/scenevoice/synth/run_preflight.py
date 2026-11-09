from collections.abc import Callable, Mapping
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.synth.audio_rel_path import audio_rel_path
from scenevoice.synth.check_audio_dir_full import check_audio_dir_full
from scenevoice.synth.check_audio_dir_scene import check_audio_dir_scene
from scenevoice.synth.check_limits import check_limits
from scenevoice.synth.check_out_dir_exists import check_out_dir_exists
from scenevoice.synth.check_out_path import check_out_path
from scenevoice.synth.check_record_path import check_record_path
from scenevoice.synth.check_scene import check_scene
from scenevoice.synth.check_scene_target import check_scene_target
from scenevoice.synth.find_collisions import find_collisions
from scenevoice.synth.load_plan import load_plan
from scenevoice.synth.load_record import load_record
from scenevoice.synth.preflight_result import PreflightResult
from scenevoice.synth.prepare_out_dir import prepare_out_dir
from scenevoice.synth.probe_out_dir import probe_out_dir
from scenevoice.synth.provider_registry import VERTEX, BodyCheck, ProviderSpec
from scenevoice.synth.read_plan_input import read_plan_input
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_settings import RecordSettings
from scenevoice.synth.regen_notes import missing_entry_note, missing_record_note
from scenevoice.synth.resolve_env import resolve_env
from scenevoice.synth.settings_mismatch import settings_mismatch
from scenevoice.validation import Violation


def _text(violation: Violation) -> str:
    suffix = f" (line {violation.line})" if violation.line is not None else ""
    return violation.message + suffix


def run_preflight(
    plan_path: str | Path | None,
    stdin,
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    out_dir: str | Path,
    scene: int | None = None,
    *,
    spec: ProviderSpec = VERTEX,
    body_check: BodyCheck | None = None,
    settings: RecordSettings | None = None,
    note: Callable[[str], None] = lambda text: None,
) -> PreflightResult | str:
    """Contract steps 1-7 in order; the first failure returns its message (no prefix, no key values).

    Only the scene-mode settings mismatch echoes values: the recorded and passed voice, model,
    language and instruction.
    """
    if plan_path is None:
        try:
            interactive = stdin.isatty()
        except (AttributeError, ValueError):
            return "no PLAN given and stdin is not readable"
        if interactive:
            return "no PLAN given and stdin is a terminal"
    data = read_plan_input(plan_path, stdin)
    if isinstance(data, Violation):
        return _text(data)
    scenes = load_plan(data)
    if isinstance(scenes, Violation):
        return _text(scenes)
    limit = check_limits(scenes, body_check=body_check)
    if limit is not None:
        return _text(limit)
    if scene is not None:
        out_of_range = check_scene(scene, len(scenes))
        if out_of_range is not None:
            return _text(out_of_range)
    env = resolve_env(process_env, dotenv_path, spec.env_names)
    if isinstance(env, Violation):
        return _text(env)
    if isinstance(env, list):
        return "missing environment variables: " + ", ".join(env)
    if scene is not None:
        # Scene mode: --out, DIR/audio, the target, the record path, the record (with settings), then the probe.
        selected = [s for s in scenes if s.ordinal == scene]
        for check in (
            lambda: check_out_dir_exists(out_dir),
            lambda: check_audio_dir_scene(out_dir),
            lambda: check_scene_target(out_dir, scene),
            lambda: check_record_path(out_dir),
        ):
            violation = check()
            if violation is not None:
                return _text(violation)
        entries: tuple[RecordEntry, ...] = ()
        if settings is not None:
            loaded = load_record(Path(out_dir))
            if isinstance(loaded, Violation):
                return _text(loaded)
            if loaded is None:
                note(missing_record_note(scene))
            else:
                entries = loaded
                recorded = next((e for e in entries if e.ordinal == scene), None)
                if recorded is None:
                    note(missing_entry_note(scene))
                else:
                    mismatch = settings_mismatch(scene, recorded, settings)
                    if mismatch is not None:
                        return mismatch
        unwritable = probe_out_dir(Path(out_dir) / AUDIO_DIR)
        if unwritable is not None:
            return _text(unwritable)
        return PreflightResult(selected, env, len(scenes), entries, plan=tuple(scenes))
    not_dir = check_out_path(out_dir)
    if not_dir is not None:
        return _text(not_dir)
    bad_audio = check_audio_dir_full(out_dir)
    if bad_audio is not None:
        return _text(bad_audio)
    taken = find_collisions(out_dir, [s.ordinal for s in scenes])
    if taken:
        return "output already exists: " + ", ".join(audio_rel_path(n) for n in taken)
    bad_record = check_record_path(out_dir)
    if bad_record is not None:
        return _text(bad_record)
    prepared = prepare_out_dir(Path(out_dir) / AUDIO_DIR)
    if prepared is not None:
        return _text(prepared)
    return PreflightResult(scenes, env, len(scenes), plan=tuple(scenes))
