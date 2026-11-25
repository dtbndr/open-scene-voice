from scenevoice.cli.pack_args import _PlanAndDir
from scenevoice.cli.progress_arg import add_progress_argument


def add_align_parser(subparsers) -> None:
    align = subparsers.add_parser(
        "align",
        usage="%(prog)s [-h] [--progress {text,json}] [PLAN] DIR",
        allow_abbrev=False,
        help="write line_timings.json in DIR from DIR/synth_record.json or hosted transcription",
        description="Writes DIR/line_timings.json. Start times come from DIR/synth_record.json "
        "where the contract allows it, and otherwise from one hosted OpenRouter transcription "
        "call per transcribed scene, which needs OPENROUTER_API_KEY "
        '(from the environment, the key file or .env; see "scenevoice keys").',
    )
    align.set_defaults(plan=None)
    add_progress_argument(align)
    align.add_argument(
        "paths", nargs="+", action=_PlanAndDir, metavar="[PLAN] DIR",
        help="optional plan JSON file (default: stdin), then the pack folder holding the WAV files in DIR/audio",
    )
