import argparse

from scenevoice.progress import PROGRESS_MODES


def add_progress_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--progress",
        choices=PROGRESS_MODES,
        default="text",
        help="progress format: text (default) or json (JSON lines on stderr)",
    )
