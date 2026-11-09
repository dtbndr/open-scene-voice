from pathlib import Path

from scenevoice.pack.build_manifest import build_manifest
from scenevoice.pack.build_timeline import build_timeline
from scenevoice.pack.check_line_timings import check_line_timings
from scenevoice.pack.check_no_collision import check_no_collision
from scenevoice.pack.check_no_timeline_collision import check_no_timeline_collision
from scenevoice.pack.check_pack_audio_dir import check_pack_audio_dir
from scenevoice.pack.check_pack_dir import check_pack_dir
from scenevoice.pack.check_pack_plan import check_pack_plan
from scenevoice.pack.manifest_name import MANIFEST_NAME
from scenevoice.pack.ordered_notes import ordered_notes
from scenevoice.pack.timeline_constants import SAMPLE_FRAMES_PER_TIMELINE_FRAME
from scenevoice.pack.timeline_name import TIMELINE_NAME
from scenevoice.pack.timings_freshness import TimingsFreshness
from scenevoice.pack.write_manifest import write_manifest
from scenevoice.pack.write_pack_files import write_pack_files
from scenevoice.synth import load_scene_wavs
from scenevoice.synth.one_line import one_line


def _say(stderr, text: str) -> None:
    """One ASCII-safe line: non-ASCII and surrogate-escaped characters become backslash escapes."""
    stderr.write(one_line(text).encode("ascii", "backslashreplace").decode("ascii") + "\n")


def _fail(stderr, message: str) -> int:
    _say(stderr, f"scenevoice pack: FAIL {message}")
    return 1


def _stdin_problem(stdin) -> str | None:
    try:
        interactive = stdin.isatty()
    except (AttributeError, ValueError):
        return "no PLAN given and stdin is not readable"
    return "no PLAN given and stdin is a terminal" if interactive else None


def run_pack(
    plan_path: str | Path | None, stdin, directory: str | Path, stderr, editor: str | None = None
) -> int:
    """Terminal-stdin rule, then checks 1 to 5 in contract order; one stderr line; returns the exit code."""
    if plan_path is None:
        problem = _stdin_problem(stdin)
        if problem is not None:
            return _fail(stderr, problem)
    scenes = check_pack_plan(plan_path, stdin)
    if isinstance(scenes, str):
        return _fail(stderr, scenes)
    checks = [check_pack_dir, check_pack_audio_dir, check_no_collision]
    if editor is not None:
        checks.append(check_no_timeline_collision)
    for check in checks:
        message = check(directory)
        if message is not None:
            return _fail(stderr, message)
    min_frames = SAMPLE_FRAMES_PER_TIMELINE_FRAME if editor is not None else 0
    wavs = load_scene_wavs(scenes, directory, min_frames)
    if isinstance(wavs, str):
        return _fail(stderr, wavs)
    frames = [wav.frames for wav in wavs]
    freshness = TimingsFreshness()
    missing_file = False
    if editor is not None:
        checked = check_line_timings(directory, scenes, wavs)
        if isinstance(checked, str):
            return _fail(stderr, checked)
        freshness, missing_file = checked
    manifest = build_manifest(scenes, frames)
    root = Path(directory)
    if editor is None:
        message = write_manifest(directory, manifest)
        written = f"{root / MANIFEST_NAME}"
    else:
        timeline, skipped = build_timeline(scenes, frames, freshness.fresh)
        for note in ordered_notes(freshness, missing_file, skipped):
            _say(stderr, note)
        message = write_pack_files(directory, manifest, timeline)
        written = f"{root / MANIFEST_NAME} and {root / TIMELINE_NAME}"
    if message is not None:
        return _fail(stderr, message)
    _say(stderr, f"scenevoice pack: OK {len(scenes)} scenes written to {written}")
    return 0
