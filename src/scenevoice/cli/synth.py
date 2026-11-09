import logging
import os
import sys
from pathlib import Path

from scenevoice.synth import ProviderFactory, run_synth


def run_synth_command(args, provider_factory: ProviderFactory) -> int:
    # python-dotenv warns on malformed lines (possibly echoing .env content) to
    # stderr; every stderr line must be a `scenevoice synth:` line instead.
    logging.getLogger("dotenv.main").disabled = True
    return run_synth(
        plan_path=args.plan,
        stdin=sys.stdin,
        process_env=os.environ,
        dotenv_path=Path(".env"),
        out_dir=args.out,
        voice=args.voice,
        model=args.model,
        language=args.language,
        instruction=args.instruction,
        scene=args.scene,
        provider_factory=provider_factory,
        stderr=sys.stderr,
    )
