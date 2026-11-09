from scenevoice.validation.violation import Violation


def check_cr(text: str) -> Violation | None:
    index = text.find("\r")
    if index == -1:
        return None
    line = 1 + text.count("\n", 0, index)
    return Violation("cr", "carriage return (CR, U+000D) found; use LF line endings", line)
