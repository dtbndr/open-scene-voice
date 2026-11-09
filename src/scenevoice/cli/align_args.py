from scenevoice.cli.pack_args import _PlanAndDir


def add_align_parser(subparsers) -> None:
    align = subparsers.add_parser(
        "align",
        usage="%(prog)s [-h] [PLAN] DIR",
        allow_abbrev=False,
        help="write line_timings.json in DIR from DIR/synth_record.json or hosted transcription",
        description="Writes DIR/line_timings.json. Start times come from DIR/synth_record.json "
        "where the contract allows it, and otherwise from one hosted OpenRouter transcription "
        "call per transcribed scene, which needs OPENROUTER_API_KEY (from the environment or .env).",
    )
    align.set_defaults(plan=None)
    align.add_argument(
        "paths", nargs="+", action=_PlanAndDir, metavar="[PLAN] DIR",
        help="optional plan JSON file (default: stdin), then the pack folder holding the WAV files in DIR/audio",
    )
