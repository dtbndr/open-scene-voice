import sys


def cli_argv_prefix() -> list[str]:
    """Argv prefix that runs the CLI in an isolated, UTF-8 child interpreter."""
    return [sys.executable, "-I", "-X", "utf8", "-m", "scenevoice"]
