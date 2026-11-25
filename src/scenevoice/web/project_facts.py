from dataclasses import dataclass

from .audio_scan import AudioScan
from .planned_scene import PlannedScene
from .record_read import RecordRead
from .timings_read import TimingsRead


@dataclass(frozen=True)
class ProjectFacts:
    """What the disk says about one project: the one input of `job_availability`.

    `script` is `none` (no script), `problem` (the plan refused it) or `ok`; `scenes` are the plan's scenes (empty
    unless the script is ok); `beats` is the state of `read_beats_state`.
    """

    script: str
    scenes: tuple[PlannedScene, ...]
    audio: AudioScan
    record: RecordRead
    timings: TimingsRead
    beats: str
