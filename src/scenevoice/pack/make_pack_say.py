from collections.abc import Callable

from scenevoice.progress import split_line, write_event
from scenevoice.synth.one_line import one_line


def make_pack_say(stderr, progress_mode: str = "text") -> Callable[..., None]:
    """A one-line, ASCII-safe stderr writer for texts that carry the `scenevoice pack: ` prefix.

    Text mode writes the text as given and ignores `fields`. JSON mode writes one event object:
    the prefix and event word are split off, and `fields` (kind) go to write_event as given.
    """

    def say(text: str, **fields: object) -> None:
        line = one_line(text)
        if progress_mode != "json":
            stderr.write(line.encode("ascii", "backslashreplace").decode("ascii") + "\n")
            return
        event, message = split_line("pack", line)
        write_event(stderr, "pack", event, message, **fields)

    return say
