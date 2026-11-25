import os
from collections.abc import Callable

from scenevoice.keys.key_file_path import key_file_path
from scenevoice.web import absolute_keys_file, run_web


def run_web_command(args, browser_opener: Callable[[str], object]) -> int:
    return run_web(
        port=args.port,
        no_open=args.no_open,
        opener=browser_opener,
        environ=os.environ,
        key_file=key_file_path(absolute_keys_file(os.environ)),
    )
