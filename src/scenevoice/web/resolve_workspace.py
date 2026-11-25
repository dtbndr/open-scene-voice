from collections.abc import Mapping
from pathlib import Path

from .default_workspace import default_workspace
from .workspace_error import WorkspaceError

_VARIABLE = "SCENEVOICE_WORKSPACE"


def resolve_workspace(environ: Mapping[str, str], override: Path | None = None, home: Path | None = None) -> Path:
    """The workspace path, absolute and unresolved; no filesystem access.

    An injected `override` wins, then a non-blank `SCENEVOICE_WORKSPACE`, then the default under `home`.
    """
    if override is not None:
        value = str(override)
    else:
        value = environ.get(_VARIABLE, "").strip()
        if not value:
            return default_workspace(Path.home() if home is None else home)
    if value.startswith("~") or not Path(value).is_absolute():
        raise WorkspaceError(f"{_VARIABLE} must be an absolute path, such as /Users/you/SceneVoice.")
    return Path(value)
