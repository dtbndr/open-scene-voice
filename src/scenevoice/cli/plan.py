import sys
from pathlib import Path

from scenevoice.plan import serialize_plan
from scenevoice.progress import split_line, write_event
from scenevoice.validation import Violation, load_scenes
from scenevoice.validation.regular_file_problem import regular_file_problem


def _say(text: str, progress_mode: str, **fields: object) -> None:
    if progress_mode == "json":
        event, message = split_line("plan", text)
        write_event(sys.stderr, "plan", event, message, **fields)
    else:
        print(text, file=sys.stderr)


def _fail(text: str, progress_mode: str, line: int | None = None) -> int:
    _say(
        text,
        progress_mode,
        kind="invalid_input",
        scene=None,
        line=line,
        status=None,
    )
    return 1


def run_plan(file_path: str, *, progress_mode: str = "text") -> int:
    problem = regular_file_problem(file_path)
    if problem is not None:
        return _fail(
            f"scenevoice plan: FAIL {file_path}: cannot read file ({problem})", progress_mode
        )
    try:
        data = Path(file_path).read_bytes()
    except OSError as exc:
        return _fail(
            f"scenevoice plan: FAIL {file_path}: cannot read file ({exc.strerror})",
            progress_mode,
        )
    result = load_scenes(data)
    if isinstance(result, Violation):
        violation = result
        suffix = f" (line {violation.line})" if violation.line is not None else ""
        return _fail(
            f"scenevoice plan: FAIL {file_path}: {violation.message}{suffix}",
            progress_mode,
            violation.line,
        )
    plan_bytes = serialize_plan(result).encode("utf-8")
    sys.stdout.buffer.write(plan_bytes)
    sys.stdout.buffer.flush()
    _say(f"scenevoice plan: OK {file_path}", progress_mode)
    return 0
