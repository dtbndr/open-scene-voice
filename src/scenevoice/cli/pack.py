import sys

from scenevoice.pack import run_pack


def run_pack_command(args) -> int:
    return run_pack(args.plan, sys.stdin, args.dir, sys.stderr, args.editor)
