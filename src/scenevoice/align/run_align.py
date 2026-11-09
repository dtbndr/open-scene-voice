from collections.abc import Mapping
from pathlib import Path

from scenevoice.align.align_scene import align_scene
from scenevoice.align.check_timings_path import check_timings_path
from scenevoice.align.format_notes import format_notes
from scenevoice.align.format_ok import format_ok
from scenevoice.align.match_constants import ALIGN_ENV_NAMES
from scenevoice.align.route_record import route_record
from scenevoice.align.serialize_timings import serialize_timings
from scenevoice.align.transcriber import TranscriberFactory
from scenevoice.align.write_timings_file import write_timings_file
from scenevoice.pack import (
    SAMPLE_FRAMES_PER_TIMELINE_FRAME,
    check_pack_audio_dir,
    check_pack_dir,
    check_pack_plan,
)
from scenevoice.synth import (
    load_scene_wavs,
    one_line,
    redact_secret,
    resolve_env,
)
from scenevoice.validation import Violation

_KEY = ALIGN_ENV_NAMES[0]
_PREFIX = "scenevoice align: "


def run_align(
    plan_path: str | Path | None,
    stdin,
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    directory: str | Path,
    transcriber_factory: TranscriberFactory,
    stderr,
) -> int:
    """Checks 2 to 8 in contract order; stdout stays empty; returns 0 or 1."""
    secrets = [process_env.get(_KEY)]

    def say(text: str) -> None:
        for secret in secrets:
            text = redact_secret(text, secret)
        line = one_line(_PREFIX + text)
        stderr.write(line.encode("ascii", "backslashreplace").decode("ascii") + "\n")

    def fail(text: str) -> int:
        say("FAIL " + text)
        return 1

    if plan_path is None:
        try:
            interactive = stdin.isatty()
        except (AttributeError, ValueError):
            return fail("no PLAN given and stdin is not readable")
        if interactive:
            return fail("no PLAN given and stdin is a terminal")
    scenes = check_pack_plan(plan_path, stdin)
    if isinstance(scenes, str):
        return fail(scenes)
    for check in (check_pack_dir, check_pack_audio_dir, check_timings_path):
        problem = check(directory)
        if problem is not None:
            return fail(problem)
    wavs = load_scene_wavs(scenes, directory, SAMPLE_FRAMES_PER_TIMELINE_FRAME)
    if isinstance(wavs, str):
        return fail(wavs)
    routing = route_record(scenes, wavs, directory)
    if isinstance(routing, str):
        return fail(routing)
    transcriber = None
    if any(route is None for route in routing.routes):
        env = resolve_env(process_env, dotenv_path, ALIGN_ENV_NAMES)
        if isinstance(env, Violation):
            return fail(env.message)
        if isinstance(env, list):
            return fail(f"{_KEY} is not set")
        key = env[_KEY]
        secrets.append(key)
        transcriber = transcriber_factory(key)
    results = []
    for scene, wav, route in zip(scenes, wavs, routing.routes, strict=True):
        if route is not None:
            results.append(route)
            continue
        assert transcriber is not None
        outcome = align_scene(scene, wav, transcriber)
        if isinstance(outcome, str):
            return fail(f"scene {scene.ordinal}: {outcome}")
        results.append(outcome)
    for note in format_notes(results, routing):
        say(note)
    problem = write_timings_file(directory, serialize_timings(results))
    if problem is not None:
        return fail(problem)
    say(format_ok(results, routing))
    return 0
