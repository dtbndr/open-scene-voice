import sys


def read_key_value(name: str) -> tuple[str | None, str | None]:
    """(value, problem). Refuses a terminal before reading; strips exactly one trailing newline."""
    if sys.stdin is None or sys.stdin.isatty():
        return None, f"{name}: pipe the value in, for example printf %s VALUE | scenevoice keys set {name}"
    data = sys.stdin.buffer.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, f"{name}: the value is not valid UTF-8"
    if text.startswith("\ufeff"):
        return None, f"{name}: the value starts with a byte-order mark"
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return text, None
