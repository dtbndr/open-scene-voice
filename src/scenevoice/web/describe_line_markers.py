from .audio_scan import AudioScan
from .classify_line_markers import classify_line_markers
from .listen_scenes import listen_scenes
from .planned_scene import PlannedScene
from .record_read import RecordRead
from .timings_read import TimingsRead


def describe_line_markers(
    scenes: tuple[PlannedScene, ...], audio: AudioScan, record: RecordRead, timings: TimingsRead
) -> dict[str, object]:
    """The `line_markers` object: state, the stale scene numbers and the estimate of scenes align would listen to.

    Without a plan (no usable script) no scene can be judged: a readable file is reported stale with no scene list.
    """
    state, stale = classify_line_markers(tuple(scene.ordinal for scene in scenes), timings, audio.hashes)
    if not scenes and state == "fresh":
        state = "stale"
    return {"state": state, "stale_scenes": list(stale), "listen_scenes": listen_scenes(scenes, record, audio.hashes)}
