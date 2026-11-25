from pathlib import Path

from scenevoice.cli.keys_say import note, say
from scenevoice.keys import remove_key
from scenevoice.validation import Violation


def run_keys_remove(name: str, path: Path) -> int:
    outcome = remove_key(path, name, note)
    if isinstance(outcome, Violation):
        say(f"FAIL {outcome.message}")
        return 1
    if outcome == "removed":
        say(f"removed {name}")
    else:
        say(f"{name} was not saved")
    return 0
