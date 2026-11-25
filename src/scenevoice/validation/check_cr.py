from scenevoice.validation.violation import Violation


def check_cr(text: str) -> Violation | None:
    index = text.find("\r")
    if index == -1:
        return None
    line = 1 + text.count("\n", 0, index)
    return Violation("cr", "This line ends in a Windows-style line break. Save the script with normal line endings.", line)
