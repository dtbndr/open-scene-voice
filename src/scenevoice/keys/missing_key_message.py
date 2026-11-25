from collections.abc import Sequence
from pathlib import Path


def missing_key_message(names: Sequence[str], key_file: str | Path | None) -> str:
    """Names only, in the order given, never values. The command uses the first name; `names` must be non-empty."""
    many = len(names) > 1
    sentence = f'Missing: {", ".join(names)}. Add {"them" if many else "it"} with "scenevoice keys set {names[0]}"'
    if key_file is None:
        return sentence + "."
    return f'{sentence}, or put {"them" if many else "it"} in {key_file}.'
