import re
from typing import Literal

SINGLE_RANGE = re.compile(r"bytes=([0-9]*)-([0-9]*)")
BEYOND_ANY_FILE = 10**18  # a longer digit string is clamped to this: no int() of thousands of digits


def _number(digits: str) -> int:
    return int(digits) if len(digits) <= 18 else BEYOND_ANY_FILE


def parse_range(header: str | None, size: int) -> tuple[int, int] | Literal["ignore", "unsatisfiable"]:
    """One `Range: bytes=a-b | a- | -n` as an inclusive `(start, end)` within `size` bytes.

    "unsatisfiable" when no byte is selected (416); "ignore" for anything else that is not one well-formed range
    (the full body is served, as the RFC allows).
    """
    found = SINGLE_RANGE.fullmatch(header) if header is not None else None
    if found is None:
        return "ignore"
    first, last = found.groups()
    if not first:
        if not last:
            return "ignore"
        count = _number(last)  # suffix: the last `count` bytes
        if count == 0 or size == 0:
            return "unsatisfiable"
        return max(size - count, 0), size - 1
    start = _number(first)
    end = _number(last) if last else BEYOND_ANY_FILE
    if end < start:
        return "ignore"
    if start >= size:
        return "unsatisfiable"
    return start, min(end, size - 1)
