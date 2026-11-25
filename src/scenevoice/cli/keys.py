import json
import logging
import os

from scenevoice.cli.keys_remove import run_keys_remove
from scenevoice.cli.keys_say import note, say
from scenevoice.cli.keys_set import run_keys_set
from scenevoice.keys import key_file_path, read_key_file
from scenevoice.keys.key_status import key_status
from scenevoice.validation import Violation


def run_keys_command(args) -> int:
    # python-dotenv may echo .env content on malformed lines; every stderr line
    # must be a `scenevoice keys:` line instead.
    logging.getLogger("dotenv.main").disabled = True
    path = key_file_path(os.environ)
    if args.keys_command == "set":
        return run_keys_set(args.name, path)
    if args.keys_command == "remove":
        return run_keys_remove(args.name, path)
    raw = read_key_file(path, note)
    if isinstance(raw, Violation):
        say(f"FAIL {raw.message}")
        return 1
    print(json.dumps({"path": str(path), "keys": key_status(raw)}, ensure_ascii=False))
    return 0
