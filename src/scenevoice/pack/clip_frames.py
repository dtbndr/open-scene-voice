from scenevoice.pack.timeline_constants import SAMPLE_FRAMES_PER_TIMELINE_FRAME


def clip_frames(wav_frames: int) -> int:
    return wav_frames // SAMPLE_FRAMES_PER_TIMELINE_FRAME
