from pathlib import Path

from .planned_scene import PlannedScene
from .project_facts import ProjectFacts
from .read_beats_state import read_beats_state
from .read_line_timings import read_line_timings
from .read_record import read_record
from .scan_audio import scan_audio


def read_project_facts(
    directory: Path, key_file: Path | None, script: str, scenes: tuple[PlannedScene, ...], revision: str | None
) -> ProjectFacts:
    """What the disk says about one project, given the script state and the plan's scenes already known."""
    audio, record, timings = scan_audio(directory, key_file), read_record(directory, key_file), read_line_timings(directory, key_file)
    return ProjectFacts(script, scenes, audio, record, timings, read_beats_state(directory, revision, key_file))
