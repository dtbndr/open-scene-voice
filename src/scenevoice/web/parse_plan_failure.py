import json
from typing import Any

from .plan_problem import PlanProblem

FALLBACK = "This script has a problem the checker could not describe."
_UNREADABLE = "cannot read file"


def _events(stderr: str) -> list[dict[str, Any]]:
    events = []
    for text in stderr.split("\n"):  # never splitlines: U+2028 and U+0085 may sit inside a JSON string
        try:
            event = json.loads(text)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def parse_plan_failure(stderr: str, temp_path: str) -> PlanProblem | None:
    """The script problem from the last `fail` event of `plan --progress json`, or None when it is not one.

    None means a server-side outcome (another kind of fail, an unreadable temp file, no usable event). The temp
    path is removed from the message; when it is absent the event message is never echoed.
    """
    failures = [event for event in _events(stderr) if event.get("event") == "fail"]
    if not failures or failures[-1].get("kind") != "invalid_input":
        return None
    event = failures[-1]
    message = event.get("message")
    if not isinstance(message, str):
        return None
    line = event.get("line")
    line = line if isinstance(line, int) and not isinstance(line, bool) else None
    prefix = f"{temp_path}: "
    if not message.startswith(prefix):
        return PlanProblem(line, FALLBACK)
    message = message[len(prefix) :]
    if message.startswith(_UNREADABLE):
        return None
    suffix = f" (line {line})"
    if line is not None and message.endswith(suffix):
        message = message[: -len(suffix)]
    return PlanProblem(line, message)
