import os
from collections.abc import Callable
from pathlib import Path

from .audio_file_name import audio_file_name
from .error_envelope import error_envelope
from .open_regular_file import open_regular_file
from .parse_range import parse_range
from .project_dir import project_dir
from .regular_file import regular_file
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root
from .workspace_error import FileTooLargeError

AUDIO_CAP = 256 * 1024 * 1024
NOT_FOUND = "That audio file does not exist."
TOO_LARGE = "That audio file is larger than 256 MiB, so it cannot be played here."
UNSATISFIABLE = "That part of the audio file does not exist."
BASE_HEADERS = (("Content-Type", "audio/wav"), ("Accept-Ranges", "bytes"))


def _read_slice(fd: int, start: int, count: int) -> bytes:
    os.lseek(fd, start, os.SEEK_SET)
    chunks: list[bytes] = []
    while count > 0:
        chunk = os.read(fd, count)
        if not chunk:
            break
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def _serve(path: Path, range_header: str | None, key_file: Path | None) -> Response:
    try:
        opened = open_regular_file(path, AUDIO_CAP, key_file)
    except FileTooLargeError:
        return error_envelope("bad_request", TOO_LARGE, status=413)
    if opened is None:
        return error_envelope("not_found", NOT_FOUND)
    fd, size = opened
    try:
        chosen = parse_range(range_header, size)
        if chosen == "unsatisfiable":
            return error_envelope(
                "bad_request", UNSATISFIABLE, status=416, headers=(("Content-Range", f"bytes */{size}"),)
            )
        if chosen == "ignore":
            return Response(200, _read_slice(fd, 0, size), BASE_HEADERS, no_store=True)
        start, end = chosen
        headers = (*BASE_HEADERS, ("Content-Range", f"bytes {start}-{end}/{size}"))
        return Response(206, _read_slice(fd, start, end - start + 1), headers, no_store=True)
    except OSError:
        return error_envelope("not_found", NOT_FOUND)
    finally:
        os.close(fd)


def serve_audio(root_getter: Callable[[], Path], project_id: str, file: str, key_file: Path | None) -> Handler:
    """GET /api/projects/{id}/audio/{file}: one allowlisted `NNN.wav` with a single `Range`; writes nothing."""

    def handle(request: Request) -> Response:
        if not audio_file_name(file):  # refused before any filesystem call
            return error_envelope("not_found", NOT_FOUND)

        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", NOT_FOUND)
            path = regular_file(directory, "audio", file, key_file=key_file)
            if path is None:
                return error_envelope("not_found", NOT_FOUND)
            return _serve(path, request.header("range"), key_file)

        return with_root(root_getter, use)

    return handle
