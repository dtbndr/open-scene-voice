"""Render one progress event as a single ASCII JSON line."""

import json

from scenevoice.progress.kinds import KINDS

COMMANDS = ("plan", "synth", "align", "pack", "beats")
EVENTS = ("scene", "note", "ok", "fail")

_SCENE_REQUIRED = ("state", "scene", "total")
_SCENE_OPTIONAL = ("path",)
_FAIL_FIELDS = ("kind", "scene", "line", "status")


def event_line(command: str, event: str, message: str, **fields: object) -> str:
    """Return the event as one JSON line ending in a newline.

    Raises ValueError for an unknown command, event or field, or for a
    missing or invalid required field.
    """
    if command not in COMMANDS:
        raise ValueError(f"unknown command: {command!r}")
    if event not in EVENTS:
        raise ValueError(f"unknown event: {event!r}")
    body: dict[str, object] = {"command": command, "event": event, "message": message}
    if event == "scene":
        body.update(_scene_fields(fields))
    elif event == "fail":
        body.update(_fail_fields(fields))
    elif fields:
        raise ValueError(f"unknown fields for {event}: {sorted(fields)}")
    return json.dumps(body, ensure_ascii=True, separators=(",", ":")) + "\n"


def _scene_fields(fields: dict[str, object]) -> dict[str, object]:
    allowed = _SCENE_REQUIRED + _SCENE_OPTIONAL
    extra = sorted(set(fields) - set(allowed))
    if extra:
        raise ValueError(f"unknown fields for scene: {extra}")
    missing = [name for name in _SCENE_REQUIRED if name not in fields]
    if missing:
        raise ValueError(f"missing fields for scene: {missing}")
    if fields["state"] not in ("started", "done"):
        raise ValueError(f"unknown scene state: {fields['state']!r}")
    return {name: fields[name] for name in allowed if name in fields}


def _fail_fields(fields: dict[str, object]) -> dict[str, object]:
    extra = sorted(set(fields) - set(_FAIL_FIELDS))
    if extra:
        raise ValueError(f"unknown fields for fail: {extra}")
    if fields.get("kind") not in KINDS:
        raise ValueError(f"unknown fail kind: {fields.get('kind')!r}")
    return {name: fields.get(name) for name in _FAIL_FIELDS}
