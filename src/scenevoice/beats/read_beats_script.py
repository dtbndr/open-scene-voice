from pathlib import Path

from scenevoice.beats.beats_constants import MAX_SCRIPT_CHARS, SCRIPT_TOO_LONG_MESSAGE
from scenevoice.validation import Violation, load_scenes
from scenevoice.validation.decode_script import decode_script
from scenevoice.validation.regular_file_problem import regular_file_problem
from scenevoice.validation.scene import Scene

# A UTF-8 character is at most 4 bytes, so a longer file is over the cap.
_READ_LIMIT = 4 * MAX_SCRIPT_CHARS


def _plan_check_message(violation: Violation) -> str:
    suffix = f" (line {violation.line})" if violation.line is not None else ""
    return f"it does not pass the plan check: {violation.message}{suffix}"


def read_beats_script(path: str | Path) -> tuple[bytes, list[Scene]] | str:
    """The script bytes (read once, bounded) and its scenes, or a one-line refusal."""
    problem = regular_file_problem(path)
    if problem is not None:
        return f"could not read the script {path} ({problem})"
    try:
        with open(path, "rb") as handle:
            data = handle.read(_READ_LIMIT + 1)
    except (OSError, ValueError) as error:
        reason = getattr(error, "strerror", None) or "unreadable"
        return f"could not read the script {path} ({reason})"
    if len(data) > _READ_LIMIT:
        return SCRIPT_TOO_LONG_MESSAGE
    decoded = decode_script(data)
    if isinstance(decoded, Violation):
        return _plan_check_message(decoded)
    if len(decoded) > MAX_SCRIPT_CHARS:
        return SCRIPT_TOO_LONG_MESSAGE
    scenes = load_scenes(data)
    if isinstance(scenes, Violation):
        return _plan_check_message(scenes)
    return data, scenes
