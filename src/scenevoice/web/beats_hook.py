from collections.abc import Callable
from pathlib import Path

from .remove_candidate import remove_candidate
from .swap_beats import swap_beats


def beats_hook(
    directory: Path, candidate: Path, revision: str, redo: bool, key_file: Path | None
) -> Callable[[str, int], tuple[str | None, str | None]]:
    """The job's `on_finish` for `beats` and `beats-redo`: swap a finished answer in, delete the candidate in every outcome.

    Only a job that finished (`done`, exit 0) is swapped, so a failed or cancelled run never becomes `beats.json`,
    even when the CLI wrote a complete sidecar before exiting 1 (an answer it rejected). The candidate is removed
    last and even when the swap raises; the old `beats.json` stays untouched unless the swap succeeds.
    """

    def on_finish(outcome: str, scenes_done: int) -> tuple[str | None, str | None]:
        try:
            message = swap_beats(directory, candidate, revision, redo, key_file) if outcome == "done" else None
        finally:
            remove_candidate(candidate)
        return message, None

    return on_finish
