import json
import re

from .known_kind import known_kind
from .plain_int import plain_int
from .progress_vocabulary import COMMANDS, EVENT_NAMES, SCENE_STATES

_AUDIO_PATH = re.compile(r"audio/[0-9]{3}\.wav", re.ASCII)


def parse_event_line(text: str) -> dict[str, object] | None:
    """One child stderr line as a safe event object, or None for anything that is not a known event.

    The object is built field by field from an allowlist and re-typed; nothing from the line is copied through
    as it came, so unknown fields, odd types and non-JSON text (tracebacks, argparse errors) never get out.
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):  # a deeply nested line is unreadable, not a crash
        return None
    if not isinstance(data, dict):
        return None
    event = data.get("event")
    if not isinstance(event, str) or event not in EVENT_NAMES:
        return None
    command = data.get("command")
    message = data.get("message")
    out: dict[str, object] = {
        "type": event,
        "command": command if isinstance(command, str) and command in COMMANDS else None,
        "message": message if isinstance(message, str) else "",
    }
    if event == "scene":
        state = data.get("state")
        if not isinstance(state, str) or state not in SCENE_STATES:
            return None
        out.update(state=state, scene=plain_int(data.get("scene")), total=plain_int(data.get("total")))
        path = data.get("path")
        if isinstance(path, str) and _AUDIO_PATH.fullmatch(path):
            out["path"] = path
    elif event == "fail":
        out.update(
            kind=known_kind(data.get("kind")),
            scene=plain_int(data.get("scene")),
            line=plain_int(data.get("line")),
            status=plain_int(data.get("status")),
        )
    return out
