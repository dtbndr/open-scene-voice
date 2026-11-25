import sys


def say(message: str) -> None:
    print(f"scenevoice keys: {message}", file=sys.stderr)


def note(text: str) -> None:
    say(f"NOTE {text}")
