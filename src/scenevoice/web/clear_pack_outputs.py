from pathlib import Path

from .delete_exact_files import delete_exact_files
from .error_envelope import error_envelope
from .job_context import JobContext
from .not_ordinary import NotOrdinary
from .response import Response
from .restart_messages import NOT_ORDINARY, WENT_WRONG
from .slot_handle import SlotHandle
from .start_refused import start_refused


def clear_pack_outputs(context: JobContext, directory: Path, handle: SlotHandle) -> Response | None:
    """The pack's delete-first rule: remove the old manifest and timeline (the CLI will not overwrite them), or the refusal.

    Only after every other check has passed and only while the slot is still valid (a cancel or shutdown during the plan
    deletes nothing). A name that is not an ordinary file refuses the start and deletes nothing; a failed deletion
    answers the generic error. A pack that then fails leaves the old one gone: nothing is put back.
    """
    if not context.runner.valid(handle):
        return start_refused(context.runner)
    try:
        delete_exact_files(directory, context.key_file, context.ops, pack_only=True)
    except NotOrdinary:
        return error_envelope("not_allowed", NOT_ORDINARY)
    except OSError:
        return error_envelope("internal_error", WENT_WRONG)
    return None
