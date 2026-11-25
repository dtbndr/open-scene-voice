import argparse

from scenevoice.cli.progress_arg import add_progress_argument
from scenevoice.synth import is_text_blank


def _non_blank_model(value: str) -> str:
    if is_text_blank(value):
        raise argparse.ArgumentTypeError("must not be blank")
    return value


def add_beats_parser(subparsers) -> None:
    beats = subparsers.add_parser(
        "beats",
        allow_abbrev=False,
        help="split a script's scenes into visual beats with one OpenRouter call",
        description="Splits each scene of a script into visual beats and writes them to a JSON "
        "sidecar file with one hosted OpenRouter chat call. The script text is sent to "
        "OpenRouter and uses provider quota; this needs OPENROUTER_API_KEY (from the "
        'environment, the key file or .env; see "scenevoice keys"). It never overwrites an '
        "existing file. The sidecar is not part "
        "of the script. If the reply fails its checks or is cut off at the length limit, it is "
        "saved as raw text, the command exits 1, and the file is not usable beats. A paid call "
        "is used either way.",
    )
    beats.add_argument("script", metavar="SCRIPT", help="path to the script file")
    beats.add_argument("--out", required=True, metavar="FILE", help="sidecar file to create (must not exist)")
    beats.add_argument(
        "--model", required=True, type=_non_blank_model,
        help="OpenRouter model ID used to split the beats",
    )
    add_progress_argument(beats)
