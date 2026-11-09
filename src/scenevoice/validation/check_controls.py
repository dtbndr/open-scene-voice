import re

from scenevoice.validation.violation import Violation

# Unicode category Cc (C0, DEL, C1) except LF.
_DISALLOWED = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f]")


def check_controls(text: str) -> Violation | None:
    match = _DISALLOWED.search(text)
    if match is None:
        return None
    line = 1 + text.count("\n", 0, match.start())
    return Violation("control", f"disallowed control character U+{ord(match.group()):04X}", line)
