import argparse
import sys
import webbrowser
from collections.abc import Callable

from scenevoice.align import TranscriberFactory, make_openrouter_transcriber
from scenevoice.cli.align import run_align_command
from scenevoice.cli.align_args import add_align_parser
from scenevoice.cli.beats import run_beats_command
from scenevoice.cli.beats_args import add_beats_parser
from scenevoice.cli.check_synth_args import check_synth_args
from scenevoice.cli.keys import run_keys_command
from scenevoice.cli.keys_args import add_keys_parser
from scenevoice.cli.keys_usage_error import keys_usage_error
from scenevoice.cli.pack import run_pack_command
from scenevoice.cli.pack_args import add_pack_parser
from scenevoice.cli.plan import run_plan
from scenevoice.cli.progress_arg import add_progress_argument
from scenevoice.cli.synth import run_synth_command
from scenevoice.cli.synth_args import add_synth_parser
from scenevoice.cli.web import run_web_command
from scenevoice.cli.web_args import add_web_parser
from scenevoice.openrouter import ChatFactory, make_openrouter_chat
from scenevoice.synth import ProviderFactory, make_provider
from scenevoice.synth import (
    make_vertex_provider as make_vertex_provider,  # noqa: PLC0414 (kept importable)
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scenevoice")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="print a script's scene plan as JSON")
    plan.add_argument("file_path", help="path to the plan script")
    add_progress_argument(plan)
    add_synth_parser(subparsers)
    add_align_parser(subparsers)
    add_pack_parser(subparsers)
    add_beats_parser(subparsers)
    add_keys_parser(subparsers)
    add_web_parser(subparsers)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory | None = None,
    transcriber_factory: TranscriberFactory | None = None,
    beats_factory: ChatFactory | None = None,
    browser_opener: Callable[[str], object] | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra:
        if args.command == "keys":
            # argparse would echo unrecognized tokens, which may be a pasted secret.
            keys_usage_error()
        parser.parse_args(argv)  # reproduces the default error for every other command
    if args.command == "synth":
        check_synth_args(args)
        factory = provider_factory if provider_factory is not None else make_provider
        return run_synth_command(args, factory)
    if args.command == "align":
        transcriber = (
            transcriber_factory if transcriber_factory is not None else make_openrouter_transcriber
        )
        return run_align_command(args, transcriber)
    if args.command == "pack":
        return run_pack_command(args)
    if args.command == "beats":
        beats_chat = beats_factory if beats_factory is not None else make_openrouter_chat
        return run_beats_command(args, beats_chat)
    if args.command == "keys":
        return run_keys_command(args)
    if args.command == "web":
        return run_web_command(args, browser_opener if browser_opener is not None else webbrowser.open)
    return run_plan(args.file_path, progress_mode=args.progress)
