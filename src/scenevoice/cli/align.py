import logging
import os
import sys
from pathlib import Path

from scenevoice.align import TranscriberFactory, run_align
from scenevoice.keys import key_file_path as default_key_file_path


def run_align_command(args, transcriber_factory: TranscriberFactory) -> int:
    # python-dotenv warns on malformed lines (possibly echoing .env content) to
    # stderr; every stderr line must be a `scenevoice align:` line instead.
    logging.getLogger("dotenv.main").disabled = True
    return run_align(
        args.plan,
        sys.stdin,
        os.environ,
        Path(".env"),
        args.dir,
        transcriber_factory,
        sys.stderr,
        key_file_path=default_key_file_path(os.environ),
        progress_mode=args.progress,
    )
