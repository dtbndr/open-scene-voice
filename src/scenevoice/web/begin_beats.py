from pathlib import Path

from .beats_candidate import beats_candidate
from .beats_hook import beats_hook
from .beats_start import BeatsStart
from .error_envelope import error_envelope
from .job_context import JobContext
from .job_request import JobRequest
from .regular_file import regular_file
from .response import Response
from .restart_messages import NOT_ORDINARY, WENT_WRONG
from .slot_handle import SlotHandle
from .start_refused import start_refused
from .sweep_candidates import sweep_candidates


def begin_beats(
    context: JobContext, directory: Path, handle: SlotHandle, request: JobRequest, script: bytes, revision: str
) -> Response | BeatsStart:
    """The beats-only part of a start (J9), run after every check has passed: the slot check, the sweep, the redo plain-file check, the candidate name.

    The slot must still be valid before the sweep removes anything (a cancel or shutdown during the plan stops here).
    The sweep comes before the plain-file check so a leftover second name of `beats.json` from a killed first run
    (the candidate hard-linked to it) is removed first and Redo can proceed. Redo needs `beats.json` to be an
    ordinary, singly linked file that is not the key file (it will be replaced); a symlink, a hard link or a directory
    refuses the start. The candidate is a fresh name in the project folder; `script` are the counted bytes the child
    reads from its private copy.
    """
    redo = request.kind == "beats-redo"
    if not context.runner.valid(handle):
        return start_refused(context.runner)
    try:
        sweep_candidates(directory)
    except OSError:
        return error_envelope("internal_error", WENT_WRONG)
    if redo and regular_file(directory, "beats.json", key_file=context.key_file) is None:
        return error_envelope("not_allowed", NOT_ORDINARY)
    candidate = beats_candidate(directory)
    return BeatsStart(candidate, script, beats_hook(directory, candidate, revision, redo, context.key_file))
