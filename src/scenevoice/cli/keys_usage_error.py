import sys
from typing import NoReturn

from scenevoice.keys import KEY_NAMES

KEYS_USAGE = (
    "scenevoice keys: usage: scenevoice keys status | set NAME | remove NAME "
    f"(NAME is one of: {', '.join(KEY_NAMES)}; "
    "the value for set is read from standard input)"
)


def keys_usage_error(*_ignored: object) -> NoReturn:
    """Fixed usage error: argparse's own text would echo the offending token, which may be a secret."""
    print(KEYS_USAGE, file=sys.stderr)
    sys.exit(2)
