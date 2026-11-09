from dataclasses import dataclass


@dataclass(frozen=True)
class Alignment:
    """Per-character timings from a provider, already contract-valid.

    The adapter that produces it enforces validity; consumers neither validate nor repair.
    """

    characters: tuple[str, ...]
    character_start_times_seconds: tuple[float, ...]
    character_end_times_seconds: tuple[float, ...]
