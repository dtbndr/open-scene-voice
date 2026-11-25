import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from scenevoice.keys.key_names import KEY_NAMES

from .absolute_keys_file import absolute_keys_file
from .child_env import child_env
from .cli_result import CliResult
from .delete_key import delete_key
from .get_keys import get_keys
from .put_key import put_key
from .route_table import Handler
from .run_cli import run_cli
from .suggested_region import suggested_region


def register_keys_routes(
    *,
    cwd: Path,
    environ: Mapping[str, str],
    ignored_environment: Sequence[str],
    prefix: Sequence[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, dict[str, Handler]]:
    """Route table entries for the keys API; merge into the server's table (one call per server).

    `environ` is the server's own environment: the children get it without the five key variables and with
    an absolute key-file override. The mutation lock is created here, so it is per server.
    """
    env = child_env(absolute_keys_file(environ))
    ignored = list(ignored_environment)
    region = suggested_region()
    lock = threading.Lock()

    def run(args: Sequence[str], stdin: bytes | None) -> CliResult:
        return run_cli(args, cwd=cwd, env=env, stdin=stdin, prefix=prefix, timeout=timeout)

    routes: dict[str, dict[str, Handler]] = {"/api/keys": {"GET": get_keys(run, region, ignored)}}
    for name in KEY_NAMES:
        routes[f"/api/keys/{name}"] = {
            "PUT": put_key(run, lock, region, ignored),
            "DELETE": delete_key(run, lock, region, ignored),
        }
    return routes
