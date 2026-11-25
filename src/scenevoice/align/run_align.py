from collections.abc import Mapping
from pathlib import Path

from scenevoice.align.align_scene import align_scene
from scenevoice.align.check_timings_path import check_timings_path
from scenevoice.align.format_notes import format_notes
from scenevoice.align.format_ok import format_ok
from scenevoice.align.make_align_say import make_align_say
from scenevoice.align.match_constants import ALIGN_ENV_NAMES
from scenevoice.align.route_record import route_record
from scenevoice.align.say_scene import say_scene
from scenevoice.align.serialize_timings import serialize_timings
from scenevoice.align.transcriber import TranscriberFactory
from scenevoice.align.write_timings_file import write_timings_file
from scenevoice.keys import missing_key_message
from scenevoice.pack import (
    SAMPLE_FRAMES_PER_TIMELINE_FRAME,
    check_pack_audio_dir,
    check_pack_dir,
    check_pack_plan,
)
from scenevoice.progress import Failure
from scenevoice.synth import load_scene_wavs, resolve_env
from scenevoice.validation import Violation

_KEY = ALIGN_ENV_NAMES[0]


def run_align(
    plan_path: str | Path | None,
    stdin,
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    directory: str | Path,
    transcriber_factory: TranscriberFactory,
    stderr,
    key_file_path: str | Path | None = None,
    progress_mode: str = "text",
) -> int:
    """Checks 2 to 8 in contract order; stdout stays empty; returns 0 or 1."""
    secrets = [process_env.get(_KEY)]
    say = make_align_say(stderr, secrets, progress_mode)
    json_mode = progress_mode == "json"

    def fail(text: str, kind: str) -> int:
        """`kind` is the phase-rule kind for a plain text; a Failure keeps its own."""
        if isinstance(text, Failure):  # read before say() redacts the text into a plain str
            fields = dict(kind=text.kind, scene=text.scene, line=text.line, status=text.status)
        else:
            fields = dict(kind=kind, scene=None, line=None, status=None)
        say("FAIL " + text, **fields)
        return 1

    if plan_path is None:
        try:
            interactive = stdin.isatty()
        except (AttributeError, ValueError):
            return fail("no PLAN given and stdin is not readable", "invalid_input")
        if interactive:
            return fail("no PLAN given and stdin is a terminal", "invalid_input")
    scenes = check_pack_plan(plan_path, stdin)
    if isinstance(scenes, str):
        return fail(scenes, "invalid_input")
    for check in (check_pack_dir, check_pack_audio_dir, check_timings_path):
        problem = check(directory)
        if problem is not None:
            return fail(problem, "invalid_input")
    wavs = load_scene_wavs(scenes, directory, SAMPLE_FRAMES_PER_TIMELINE_FRAME)
    if isinstance(wavs, str):
        return fail(wavs, "invalid_input")
    routing = route_record(scenes, wavs, directory)
    if isinstance(routing, str):
        return fail(routing, "invalid_input")
    transcriber = None
    if any(route is None for route in routing.routes):
        # Check 5a: the key file, like ./.env, is read only when some scene needs transcription.
        env = resolve_env(
            process_env,
            dotenv_path,
            ALIGN_ENV_NAMES,
            key_file=key_file_path,
            warn=lambda text: say("NOTE " + text),
        )
        if isinstance(env, Violation):
            return fail(env.message, "invalid_input")
        if isinstance(env, list):
            return fail(missing_key_message(env, key_file_path), "missing_key")
        key = env[_KEY]
        secrets.append(key)
        transcriber = transcriber_factory(key)
    results = []
    total = len(scenes)
    for scene, wav, route in zip(scenes, wavs, routing.routes, strict=True):
        n = scene.ordinal
        if route is not None:
            results.append(route)
            say_scene(say, json_mode, "done", n, total, f"scene {n}/{total} from synth record")
            continue
        assert transcriber is not None
        say_scene(say, json_mode, "started", n, total, f"scene {n}/{total} transcribing")
        outcome = align_scene(scene, wav, transcriber)
        if isinstance(outcome, str):
            kind = outcome.kind if isinstance(outcome, Failure) else "other"
            status = outcome.status if isinstance(outcome, Failure) else None
            return fail(Failure(f"scene {n}: {outcome}", kind=kind, scene=n, status=status), kind)
        results.append(outcome)
        say_scene(say, json_mode, "done", n, total, f"scene {n}/{total} aligned")
    for note in format_notes(results, routing):
        say(note)
    problem = write_timings_file(directory, serialize_timings(results))
    if problem is not None:
        return fail(problem, "other")
    say(format_ok(results, routing))
    return 0
