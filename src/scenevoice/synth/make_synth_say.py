from collections.abc import Callable

from scenevoice.progress import split_line, write_event
from scenevoice.synth.one_line import one_line
from scenevoice.synth.redact_secret import redact_secret

_PREFIX = "scenevoice synth: "


def make_synth_say(stderr, secrets: list[str | None], progress_mode: str) -> Callable[..., None]:
    """A redacted one-line stderr writer; secrets may grow later.

    Text mode writes `scenevoice synth: <text>` unescaped and ignores `fields`. JSON mode writes one
    event object: `fields` (kind, scene, ...) go to write_event as given, and an `event` field
    overrides the event word (used for scene events, whose text carries no OK/NOTE/FAIL word).
    """

    def say(text: str, **fields: object) -> None:
        for secret in secrets:
            text = redact_secret(text, secret)
        text = one_line(text)
        if progress_mode != "json":
            stderr.write(_PREFIX + text + "\n")
            return
        event = fields.pop("event", None)
        if event is None:
            event, text = split_line("synth", text)
        write_event(stderr, "synth", str(event), text, **fields)

    return say
