import sys
from pathlib import Path

from scenevoice.plan import serialize_plan
from scenevoice.validation import Violation, load_scenes


def run_plan(file_path: str) -> int:
    try:
        data = Path(file_path).read_bytes()
    except OSError as exc:
        print(
            f"scenevoice plan: FAIL {file_path}: cannot read file ({exc.strerror})",
            file=sys.stderr,
        )
        return 1
    result = load_scenes(data)
    if isinstance(result, Violation):
        violation = result
        suffix = f" (line {violation.line})" if violation.line is not None else ""
        print(
            f"scenevoice plan: FAIL {file_path}: {violation.message}{suffix}",
            file=sys.stderr,
        )
        return 1
    plan_bytes = serialize_plan(result).encode("utf-8")
    sys.stdout.buffer.write(plan_bytes)
    sys.stdout.buffer.flush()
    print(f"scenevoice plan: OK {file_path}", file=sys.stderr)
    return 0
