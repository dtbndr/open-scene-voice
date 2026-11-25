from collections.abc import Callable
from pathlib import Path

LENGTH_PROBLEM = "the model stopped at its length limit, so the beats may be incomplete"


def report_beats(
    say: Callable[..., None],
    out: str | Path,
    labels: list[str],
    problems: list[str],
    truncated: bool,
    scene_count: int,
    beat_count: int,
) -> int:
    """Report a written beats file; return 0 only with no problem and no cut-off."""
    if labels:
        say("NOTE cleaned: " + ", ".join(labels))
    failures = ([LENGTH_PROBLEM] if truncated else []) + problems
    for failure in failures:
        say(f"FAIL {out}: written, but {failure}", kind="other")
    if failures:
        return 1
    say(f"OK {out} ({scene_count} scenes, {beat_count} beats)")
    return 0
