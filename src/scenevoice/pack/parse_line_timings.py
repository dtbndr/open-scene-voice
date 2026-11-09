import re

from scenevoice.pack.line_timing import LineTiming
from scenevoice.pack.timings_name import TIMINGS_NAME
from scenevoice.synth.decode_json_document import decode_json_document
from scenevoice.validation import Violation

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _bad(detail: str) -> str:
    return f"{TIMINGS_NAME}: {detail}"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_line(where: str, line: object) -> LineTiming | str:
    if not isinstance(line, dict):
        return _bad(f"{where} is not an object")
    text = line.get("text")
    if not isinstance(text, str):
        return _bad(f"{where}: text is missing or not a string")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return _bad(f"{where}: text cannot be encoded as UTF-8")
    if "start_ms" not in line:
        return _bad(f"{where}: start_ms is missing")
    start = line["start_ms"]
    if start is not None and not (_is_int(start) and start >= 0):
        return _bad(f"{where}: start_ms is not a non-negative integer or null")
    return LineTiming(text, start)


def _parse_entry(
    index: int, entry: object
) -> tuple[int, str, list[LineTiming]] | str:
    where = f"scenes[{index}]"
    if not isinstance(entry, dict):
        return _bad(f"{where} is not an object")
    ordinal = entry.get("ordinal")
    if not _is_int(ordinal):
        return _bad(f"{where}: ordinal is missing or not an integer")
    sha256 = entry.get("sha256")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        return _bad(f"{where}: sha256 is not 64 lowercase hexadecimal characters")
    raw_lines = entry.get("lines")
    if not isinstance(raw_lines, list):
        return _bad(f"{where}: lines is missing or not an array")
    lines: list[LineTiming] = []
    for number, raw in enumerate(raw_lines, start=1):
        parsed = _parse_line(f"{where}.lines[{number}]", raw)
        if isinstance(parsed, str):
            return parsed
        lines.append(parsed)
    return ordinal, sha256, lines  # type: ignore[return-value]


def parse_line_timings(data: bytes) -> dict[int, tuple[str, list[LineTiming]]] | str:
    """Parse line_timings.json bytes: ordinal -> (sha256, lines), or a one-line message.

    Pure. Every entry is validated, including entries for scenes not in the plan
    (the parser does not know the plan). Unknown fields are ignored.
    """
    document = decode_json_document(data)
    if isinstance(document, Violation):
        return _bad(document.message)
    if not isinstance(document, dict):
        return _bad("top level is not an object")
    scenes = document.get("scenes")
    if not isinstance(scenes, list):
        return _bad("scenes is missing or not an array")
    table: dict[int, tuple[str, list[LineTiming]]] = {}
    for index, entry in enumerate(scenes):
        parsed = _parse_entry(index, entry)
        if isinstance(parsed, str):
            return parsed
        ordinal, sha256, lines = parsed
        if ordinal in table:
            return _bad(f"scenes[{index}]: ordinal {ordinal} is repeated")
        table[ordinal] = (sha256, lines)
    return table
