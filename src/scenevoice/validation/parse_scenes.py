from scenevoice.validation.is_blank import is_blank
from scenevoice.validation.scene import Scene
from scenevoice.validation.violation import Violation

_MARKER = "## "


def parse_scenes(text: str) -> list[Scene] | Violation:
    """Parse a script into scenes, or return the first scene violation.

    Precondition: text already passed the lexical chain (UTF-8, no BOM, no CR,
    no disallowed controls). Never call this on text that skipped it, because
    is_blank is only safe after check_controls.

    Lines split on "\\n" only (never str.splitlines(): U+2028/U+2029 must not
    split). Titles and bodies are verbatim slices, never trimmed.
    """
    lines = text.split("\n")
    markers = [i for i, line in enumerate(lines) if line.startswith(_MARKER)]
    if not markers:
        return Violation("no-marker", "no scene marker found; start each scene with '## ' at column one")
    scenes = []
    for n, start in enumerate(markers):
        end = markers[n + 1] if n + 1 < len(markers) else len(lines)
        body = "\n".join(lines[start + 1 : end])
        if end < len(lines):
            body += "\n"
        title = lines[start][len(_MARKER) :]
        line = start + 1
        if is_blank(title):
            return Violation("blank-title", "scene title is blank", line)
        if is_blank(body):
            return Violation("blank-body", "scene body is empty or only white space", line)
        scenes.append(Scene(n + 1, title, body, line))
    return scenes
