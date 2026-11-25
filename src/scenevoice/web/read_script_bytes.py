from pathlib import Path

from .exact_entry import exact_entry
from .get_script import NOT_UTF8, SCRIPT_CAP, TOO_LARGE, UNREADABLE
from .plan_problem import PlanProblem
from .read_regular_bytes import read_regular_bytes
from .script_bytes import ScriptBytes
from .workspace_error import FileTooLargeError


def read_script_bytes(directory: Path, key_file: Path | None) -> ScriptBytes:
    """The exact bytes of `script.md` (regular, at most 1 MiB, UTF-8), a problem in plain words, or nothing when absent.

    A script that is not valid UTF-8 keeps its bytes (the revision is of the saved bytes) but is a problem.
    """
    if not exact_entry(directory, "script.md"):
        return ScriptBytes()
    try:
        data = read_regular_bytes(directory / "script.md", SCRIPT_CAP, key_file)
    except FileTooLargeError:
        return ScriptBytes(None, PlanProblem(None, TOO_LARGE))
    if data is None:
        return ScriptBytes(None, PlanProblem(None, UNREADABLE))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return ScriptBytes(data, PlanProblem(None, NOT_UTF8))
    return ScriptBytes(data)
