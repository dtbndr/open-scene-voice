import os
from pathlib import Path


def key_file_overlap(workspace: str | Path, key_file: str | Path) -> bool:
    """True when `key_file` is the workspace folder or inside it, compared as casefolded normalised strings.

    Purely lexical: the filesystem is never touched, and a differently cased spelling only adds refusals.
    """
    root = os.path.normpath(str(workspace)).casefold()
    key = os.path.normpath(str(key_file)).casefold()
    return key == root or key.startswith(root.rstrip(os.sep) + os.sep)
