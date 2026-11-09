import json

from scenevoice.validation import Violation

_JSON_WHITESPACE = " \t\n\r"
_RULE = "json-document"


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> object:
    raise ValueError(f"{name} is not valid JSON")


def decode_json_document(data: bytes) -> object | Violation:
    """Strictly decode one JSON document; never raises."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return Violation(_RULE, "document is not valid UTF-8")
    if text.startswith("﻿"):
        return Violation(_RULE, "document starts with a byte order mark")
    start = len(text) - len(text.lstrip(_JSON_WHITESPACE))
    if start == len(text):
        return Violation(_RULE, "document is empty")
    decoder = json.JSONDecoder(
        object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
    )
    try:
        document, end = decoder.raw_decode(text, start)
    except RecursionError:
        return Violation(_RULE, "document is nested too deeply")
    except ValueError as exc:  # JSONDecodeError, int limit, our hooks
        return Violation(_RULE, f"document is not valid JSON ({exc})")
    if text[end:].strip(_JSON_WHITESPACE):
        return Violation(_RULE, "document has trailing data after the JSON document")
    return document
