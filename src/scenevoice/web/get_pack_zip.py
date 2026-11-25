from collections.abc import Callable
from pathlib import Path

from .build_pack_zip import PACK_CAP, build_pack_zip
from .busy_message import busy_message
from .error_envelope import error_envelope
from .job_runner import JobRunner
from .project_dir import project_dir
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root
from .workspace_error import NothingPackedError, PackTooLargeError

NO_PROJECT = "There is no project with that name."
NOTHING_PACKED = "Nothing has been packed yet."
TOO_LARGE = "The pack is larger than 1 GiB, so it cannot be downloaded here. Use Show in Finder to open the folder."


def get_pack_zip(
    root_getter: Callable[[], Path], project_id: str, key_file: Path | None, runner: JobRunner, cap: int = PACK_CAP
) -> Handler:
    """GET /api/projects/{id}/pack.zip: the allowlisted pack files as one in-memory zip; writes nothing.

    While a job holds the slot (any project) the download is 409 `busy`. Otherwise assembly runs under a zip admission
    (J2b) that excludes every start until the bytes are in memory; it is released before the body is transmitted.
    """

    def handle(request: Request) -> Response:
        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", NO_PROJECT)
            admission = runner.admit_zip()
            if admission is None:
                return error_envelope("busy", busy_message(runner.busy_reason()))
            try:
                data = build_pack_zip(directory, project_id, key_file, cap)
            except NothingPackedError:
                return error_envelope("not_found", NOTHING_PACKED)
            except PackTooLargeError:
                return error_envelope("bad_request", TOO_LARGE, status=413)
            finally:
                runner.release_zip(admission)
            headers = (
                ("Content-Type", "application/zip"),
                ("Content-Disposition", f'attachment; filename="{project_id}.zip"'),
            )
            return Response(200, data, headers, no_store=True)

        return with_root(root_getter, use)

    return handle
