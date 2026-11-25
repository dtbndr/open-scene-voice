import tempfile
from pathlib import Path


def make_launch_dir() -> Path:
    """Create an empty private (0700) working directory for one child process."""
    return Path(tempfile.mkdtemp(prefix="scenevoice-web-"))
