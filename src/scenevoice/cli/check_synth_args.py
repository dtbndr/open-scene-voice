import argparse

from scenevoice.synth import ELEVENLABS, VOICES, is_text_blank, provider_for_model


def check_synth_args(args: argparse.Namespace) -> None:
    """Post-parse step: provider-dependent checks, in the order voice, language, instruction.

    Fails through the synth subparser (usage line, then `scenevoice synth: error: ...`, exit 2).
    """
    elevenlabs = provider_for_model(args.model) is ELEVENLABS
    error = args.synth_parser.error
    if elevenlabs:
        if is_text_blank(args.voice):
            error("argument --voice: must not be blank")
        if args.language is not None:
            error("argument --language: not supported with an ElevenLabs model")
        if args.instruction is not None:
            error("argument --instruction: not supported with an ElevenLabs model")
    elif args.voice not in VOICES:
        error(f"argument --voice: invalid choice: {args.voice!r} (choose from {', '.join(VOICES)})")
