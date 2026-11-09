import argparse
import sys

from scenevoice.align import TranscriberFactory, make_openrouter_transcriber
from scenevoice.cli.align import run_align_command
from scenevoice.cli.align_args import add_align_parser
from scenevoice.cli.check_synth_args import check_synth_args
from scenevoice.cli.pack import run_pack_command
from scenevoice.cli.pack_args import add_pack_parser
from scenevoice.cli.plan import run_plan
from scenevoice.cli.synth import run_synth_command
from scenevoice.cli.synth_args import add_synth_parser
from scenevoice.synth import ProviderFactory, make_provider
from scenevoice.synth import (
    make_vertex_provider as make_vertex_provider,  # noqa: PLC0414 (kept importable)
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scenevoice")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="print a script's scene plan as JSON")
    plan.add_argument("file_path", help="path to the plan script")
    add_synth_parser(subparsers)
    add_align_parser(subparsers)
    add_pack_parser(subparsers)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory | None = None,
    transcriber_factory: TranscriberFactory | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = _build_parser().parse_args(argv)
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
    return run_plan(args.file_path)
