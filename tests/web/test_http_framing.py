import json
from io import BytesIO

import pytest
from web_http_helper import SECURITY_HEADERS, parse_response, run_handler

from scenevoice.web import (
    KEEPALIVE_COMMENT,
    Response,
    busy_message,
    content_type,
    error_envelope,
    format_sse,
    make_handler,
    parse_last_event_id,
    parse_range,
    start_stream,
    write_response,
)
from scenevoice.web.line_splitter import LineSplitter


def written(response: Response, head_only: bool = False) -> bytes:
    out = BytesIO()
    write_response(out, response, head_only=head_only)
    return out.getvalue()


@pytest.mark.parametrize(("status", "body"), [(200, b"hello"), (303, b"")])
def test_finite_responses_carry_an_exact_content_length_and_close(status: int, body: bytes) -> None:
    parsed = parse_response(written(Response(status, body)))
    assert parsed.version == "HTTP/1.0"
    assert parsed.status == status
    assert parsed.one("Content-Length") == str(len(body))
    assert parsed.body == body
    assert parsed.headers["connection"] == ["close"]
    for name, value in SECURITY_HEADERS.items():
        assert parsed.headers[name] == [value]


def test_handler_headers_are_kept_and_no_store_is_added_on_request() -> None:
    parsed = parse_response(written(Response(303, headers=(("Location", "/"),), no_store=True)))
    assert parsed.one("Location") == "/"
    assert parsed.one("Cache-Control") == "no-store"
    assert "cache-control" not in parse_response(written(Response(200))).headers


def test_head_keeps_the_length_of_the_full_body_but_sends_no_body() -> None:
    parsed = parse_response(written(Response(200, b"hello"), head_only=True))
    assert parsed.one("Content-Length") == "5"
    assert parsed.body == b""


def test_streaming_start_has_security_headers_and_close_but_no_content_length() -> None:
    out = BytesIO()
    start_stream(out, 200, headers=(("Content-Type", "text/event-stream"),), no_store=True)
    parsed = parse_response(out.getvalue())
    assert parsed.status == 200
    assert "content-length" not in parsed.headers
    assert parsed.headers["connection"] == ["close"]
    assert parsed.one("Content-Type") == "text/event-stream"
    assert parsed.one("Cache-Control") == "no-store"
    for name, value in SECURITY_HEADERS.items():
        assert parsed.headers[name] == [value]
    assert parsed.body == b""


def handler_class():
    return make_handler({"/api/ping": {"GET": lambda request: Response(200, b"pong")}}, lambda request: None, timeout=1)


def long_line() -> bytes:
    return b"GET /?token=SECRET" + b"a" * 70000 + b" HTTP/1.0\r\n\r\n"


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        (b"GARBAGE?token=SECRET\r\n\r\n", 400),
        (long_line(), 414),
    ],
)
# Key leak: the token rides the query string, so a refused request is never echoed back.
def test_parse_failures_get_the_envelope_and_headers_and_never_echo_the_request(raw: bytes, status: int) -> None:
    out = run_handler(handler_class(), raw)
    parsed = parse_response(out)
    assert parsed.status == status
    assert parsed.json()["error"]["kind"] == "bad_request"
    assert parsed.one("Content-Length") == str(len(parsed.body))
    assert parsed.headers["connection"] == ["close"]
    assert {name: parsed.headers[name][0] for name in SECURITY_HEADERS} == SECURITY_HEADERS
    assert b"SECRET" not in out


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("stale_link", 401),
        ("bad_origin", 403),
        ("not_found", 404),
        ("internal_error", 500),
    ],
)
def test_each_fixed_kind_has_its_status(kind: str, status: int) -> None:
    response = error_envelope(kind, "Plain words.")
    assert response.status == status
    assert json.loads(response.body) == {"error": {"kind": kind, "message": "Plain words."}}


@pytest.mark.parametrize("kind", ["busy"])
def test_the_job_kinds_are_409_with_the_unchanged_envelope(kind: str) -> None:
    response = error_envelope(kind, "Plain words.")
    assert response.status == 409
    assert json.loads(response.body) == {"error": {"kind": kind, "message": "Plain words."}}
    assert response.no_store is True


def test_an_event_is_an_id_line_a_data_line_and_a_blank_line() -> None:
    chunk = format_sse(3, {"seq": 7, "type": "note", "message": "hi"})
    assert chunk == b'id: 3-7\ndata: {"seq": 7, "type": "note", "message": "hi"}\n\n'


@pytest.mark.parametrize("separator", ["\n", "é"])
def test_a_message_with_any_separator_stays_on_one_ascii_data_line(separator: str) -> None:
    message = f"a{separator}b"
    chunk = format_sse(1, {"seq": 1, "type": "note", "message": message})
    chunk.decode("ascii")
    lines = chunk.decode("ascii").split("\n")
    assert len(lines) == 4  # id, data, blank, trailing empty from the final newline
    assert json.loads(lines[1][len("data: ") :])["message"] == message


def test_the_keepalive_is_a_comment_with_a_blank_line() -> None:
    assert KEEPALIVE_COMMENT == b": keepalive\n\n"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1-17", (1, 17)),
        (None, None),
        ("abc", None),
        ("1-2-3", None),
    ],
)
def test_the_last_event_id_is_read_strictly(value: str | None, expected: tuple[int, int] | None) -> None:
    assert parse_last_event_id(value) == expected


LIMIT = 8


def split_all(data: bytes, chunk: int, limit: int = LIMIT) -> list[str]:
    splitter = LineSplitter(limit)
    lines: list[str] = []
    for start in range(0, len(data), chunk):
        lines += splitter.feed(data[start : start + chunk])
    return lines + splitter.finish()


@pytest.mark.parametrize("chunk", [1, 1000])
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"a\nb\n", ["a", "b"]),
        (b"a\nlast", ["a", "last"]),  # an unterminated final line still arrives
        (b"ok\n" + b"x" * (LIMIT + 1) + b"\nafter\n", ["ok", "after"]),  # over the limit: dropped, the rest arrives
        (b"x" * LIMIT + b"\nnext\n", ["x" * LIMIT, "next"]),  # exactly the limit is kept
    ],
)
def test_lines_split_on_newline_only_and_are_independent_of_chunking(data, expected, chunk):
    assert split_all(data, chunk) == expected


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        ("synth", "SceneVoice is busy voicing."),
        ("beats", "SceneVoice is busy planning visual beats."),
        ("download", "SceneVoice is busy preparing a download."),
        ("stopping", "SceneVoice is stopping."),
    ],
)
def test_the_busy_wording_follows_the_reason_the_runner_gives(reason, message):
    assert busy_message(reason) == message


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("index.html", "text/html; charset=utf-8"),
        ("a/b.js", "text/javascript; charset=utf-8"),
        ("a.css", "text/css; charset=utf-8"),
        ("a.json", "application/json; charset=utf-8"),
    ],
)
def test_the_explicit_map(name: str, expected: str) -> None:
    assert content_type(name) == expected


@pytest.mark.parametrize("name", ["a.exe"])
def test_an_unmapped_extension_is_not_served(name: str) -> None:
    assert content_type(name) is None


SIZE = 1000


@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        ("bytes=0-99", SIZE, (0, 99)),  # P1: scrubbing audio in the player
        ("bytes=100-", SIZE, (100, 999)),
        ("bytes=-50", SIZE, (950, 999)),
        ("bytes=990-5000", SIZE, (990, 999)),  # clamped to the file end
        ("bytes=-5000", SIZE, (0, 999)),
        ("bytes=-1", 1, (0, 0)),
    ],
)
def test_a_satisfiable_single_range_is_inclusive_and_clamped(header, size, expected):
    assert parse_range(header, size) == expected


@pytest.mark.parametrize(
    ("header", "size"),
    [("bytes=1000-", SIZE), ("bytes=-0", SIZE), ("bytes=0-", 0)],
)
def test_a_range_that_selects_no_byte_is_unsatisfiable(header, size):
    assert parse_range(header, size) == "unsatisfiable"


@pytest.mark.parametrize("header", [None, "bytes=5-2", "bytes=0-1,5-6", "items=0-1", "bytes=a-b"])
def test_a_malformed_multiple_or_foreign_header_is_ignored(header):
    assert parse_range(header, SIZE) == "ignore"
