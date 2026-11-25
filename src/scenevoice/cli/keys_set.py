from pathlib import Path

from scenevoice.cli.keys_read_value import read_key_value
from scenevoice.cli.keys_say import note, say
from scenevoice.keys import set_key


def run_keys_set(name: str, path: Path) -> int:
    value, problem = read_key_value(name)
    if problem is not None or value is None:
        say(f"FAIL {problem}")
        return 1
    violation = set_key(path, name, value, note)
    if violation is not None:
        say(f"FAIL {violation.message}")
        return 1
    say(f"saved {name}")
    return 0
