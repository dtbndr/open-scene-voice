from pathlib import Path


def scrub_text(
    text: str,
    *,
    project_dir: Path | None,
    project_id: str | None,
    launch_dir: Path,
    workspace: Path,
    key_file: Path | None,
) -> str:
    """Take this machine's paths out of a child's message, longest first and by plain text (never a pattern).

    The project folder becomes the project id, the launch directory and the workspace vanish (with the slash
    after them) and the key file becomes "the key file". Each path is also matched in its `realpath` spelling,
    because a temp directory such as /var/folders resolves to /private/var/folders.
    """
    pairs: dict[str, str] = {}
    if key_file is not None:
        for spelling in _spellings(key_file):
            pairs[spelling] = "the key file"
    if project_dir is not None and project_id is not None:
        for spelling in _spellings(project_dir):
            pairs[spelling] = project_id
    for directory in (launch_dir, workspace):
        for spelling in _spellings(directory):
            pairs[spelling + "/"] = ""
            pairs[spelling] = ""
    for needle in sorted((n for n in pairs if n and n != "/"), key=len, reverse=True):
        text = text.replace(needle, pairs[needle])
    return text


def _spellings(path: Path) -> set[str]:
    spellings = {str(path)}
    try:
        spellings.add(str(path.resolve()))
    except (OSError, RuntimeError):
        pass
    return spellings
