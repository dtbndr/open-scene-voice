from pathlib import Path

from scenevoice.validation import Violation

_RULE = "plan-input"


def _unreadable(reason: str) -> Violation:
    return Violation(_RULE, f"cannot read file ({reason})")


def read_plan_input(path: str | Path | None, stdin) -> bytes | Violation:
    """Step 2: the plan bytes from `path`, or from `stdin.buffer` when no path is given."""
    if path is not None:
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            return _unreadable(exc.strerror or "unreadable")
    try:
        data = stdin.buffer.read()
    except (OSError, AttributeError, ValueError):
        return _unreadable("stdin could not be read")
    if not data:
        return _unreadable("stdin is empty")
    return data
