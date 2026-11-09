import argparse


class _PlanAndDir(argparse.Action):
    """Take one value as DIR, or two as PLAN then DIR; anything else is a usage error."""

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 2:
            parser.error(f"expected [PLAN] DIR, got {len(values)} positional arguments")
        namespace.dir = values[-1]
        namespace.plan = values[0] if len(values) == 2 else None


def add_pack_parser(subparsers) -> None:
    pack = subparsers.add_parser(
        "pack",
        usage="%(prog)s [-h] [--editor {resolve}] [PLAN] DIR",
        allow_abbrev=False,
        help="write scene_manifest.csv in DIR, beside the synthesized audio folder",
    )
    pack.set_defaults(plan=None)
    pack.add_argument(
        "--editor", choices=["resolve"], default=None,
        help="also write resolve_timeline.otio (scene markers) for DaVinci Resolve",
    )
    pack.add_argument(
        "paths", nargs="+", action=_PlanAndDir, metavar="[PLAN] DIR",
        help="optional plan JSON file (default: stdin), then the directory holding the WAV files in DIR/audio",
    )
