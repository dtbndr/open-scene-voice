from collections.abc import Callable, Sequence

from .cli_result import CliResult

# (CLI arguments, stdin bytes or None) -> result; the cwd, environment and prefix are already bound.
CliRunner = Callable[[Sequence[str], bytes | None], CliResult]
