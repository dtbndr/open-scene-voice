from collections.abc import Callable

from scenevoice.progress import split_line, write_event
from scenevoice.synth import one_line, redact_secret

_PREFIX = "scenevoice align: "


def make_align_say(stderr, secrets: list[str | None], progress_mode: str) -> Callable[..., None]:
    """A redacted one-line stderr writer; secrets may grow later.

    Text mode writes `scenevoice align: <text>` ASCII-escaped and ignores `fields`. JSON mode writes
    one event object: `fields` (kind, scene, ...) go to write_event as given, and an `event` field
    overrides the event word (used for scene events, whose text carries no OK/NOTE/FAIL word).
    """

    def say(text: str, **fields: object) -> None:
        for secret in secrets:
            text = redact_secret(text, secret)
        text = one_line(text)
        if progress_mode != "json":
            line = _PREFIX + text
            stderr.write(line.encode("ascii", "backslashreplace").decode("ascii") + "\n")
            return
        event = fields.pop("event", None)
        if event is None:
            event, text = split_line("align", text)
        write_event(stderr, "align", str(event), text, **fields)

    return say
