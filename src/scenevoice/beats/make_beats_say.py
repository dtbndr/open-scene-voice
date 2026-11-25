from collections.abc import Callable

from scenevoice.progress import split_line, write_event
from scenevoice.synth import one_line, redact_secret

_PREFIX = "scenevoice beats: "


def make_beats_say(
    stderr, secrets: list[str | None], progress_mode: str = "text"
) -> Callable[..., None]:
    """A one-line, redacted, ASCII-safe stderr writer; secrets may grow later.

    Text mode writes `scenevoice beats: <text>` and ignores `fields`. JSON mode writes one event
    object: the text is split into its event word and message, and `fields` (kind, status) go to
    write_event as given.
    """

    def say(text: str, **fields: object) -> None:
        for secret in secrets:
            text = redact_secret(text, secret)
        if progress_mode != "json":
            line = one_line(_PREFIX + text)
            stderr.write(line.encode("ascii", "backslashreplace").decode("ascii") + "\n")
            return
        event, message = split_line("beats", one_line(text))
        write_event(stderr, "beats", event, message, **fields)

    return say
