import logging
import os
import sys
from pathlib import Path

from scenevoice.beats import run_beats
from scenevoice.keys import key_file_path as default_key_file_path
from scenevoice.openrouter import ChatFactory


def run_beats_command(args, chat_factory: ChatFactory) -> int:
    # python-dotenv warns on malformed lines (possibly echoing .env content) to
    # stderr; every stderr line must be a `scenevoice beats:` line instead.
    logging.getLogger("dotenv.main").disabled = True
    return run_beats(
        args.script,
        args.out,
        args.model,
        os.environ,
        Path(".env"),
        chat_factory,
        sys.stderr,
        sys.stdout,
        key_file_path=default_key_file_path(os.environ),
        progress_mode=args.progress,
    )
