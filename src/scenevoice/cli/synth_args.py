import argparse

from scenevoice.synth import DEFAULT_LANGUAGE, MODELS, VOICES, is_text_blank


def _not_blank(value: str) -> str:
    if is_text_blank(value):
        raise argparse.ArgumentTypeError("must not be blank")
    return value


def add_synth_parser(subparsers) -> None:
    synth = subparsers.add_parser(
        "synth", help="synthesize one WAV per scene from a plan (plan JSON on stdin or PLAN)"
    )
    synth.add_argument("plan", nargs="?", default=None, help="plan JSON file (default: stdin)")
    synth.add_argument("--out", required=True, help="output directory DIR; the WAV files are written to DIR/audio")
    synth.add_argument(
        "--voice", required=True, metavar="VOICE",
        help="voice: with a Gemini model, one of the 30 prebuilt voices, exact match: "
        f"{', '.join(VOICES)}; with an ElevenLabs model, an ElevenLabs voice ID instead "
        "(checked only as non-blank)",
    )
    synth.add_argument(
        "--model", required=True, choices=MODELS,
        help="TTS model (required, no default); the provider is inferred from it: "
        "gemini-3.8-flash-tts and gemini-3.8-flash-lite-tts use Vertex, "
        "eleven_flash_v2_5 and eleven_v4 use ElevenLabs",
    )
    synth.add_argument(
        "--language", default=None, type=_not_blank,
        help=f"language code, Gemini models only (default for a Gemini model: {DEFAULT_LANGUAGE})",
    )
    synth.add_argument(
        "--instruction", default=None, type=_not_blank,
        help="delivery style instruction, Gemini models only (no default: omit it for no style); "
        "write --instruction=TEXT when TEXT starts with '-'",
    )
    synth.add_argument(
        "--scene", type=int, default=None, metavar="N",
        help="regenerates only scene N with one provider call and replaces DIR/audio/NNN.wav; "
        "--out and DIR/audio must already exist; pass the original --voice, --model, --language "
        "and --instruction again (they are checked against DIR/synth_record.json)",
    )
    synth.set_defaults(synth_parser=synth)
