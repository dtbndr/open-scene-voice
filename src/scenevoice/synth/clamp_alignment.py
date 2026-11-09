from scenevoice.synth.alignment import Alignment


def clamp_alignment(alignment: Alignment, duration: float) -> Alignment:
    """Cap every start and end time at the audio duration; characters are unchanged."""
    return Alignment(
        alignment.characters,
        tuple(min(t, duration) for t in alignment.character_start_times_seconds),
        tuple(min(t, duration) for t in alignment.character_end_times_seconds),
    )
