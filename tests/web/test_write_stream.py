
import pytest
from web_http_helper import SECURITY_HEADERS, parse_response
from web_stream_helper import ClosingChunks, RecordingWfile

from scenevoice.web import StreamResponse, write_stream

HEADERS = (("Content-Type", "text/event-stream"),)


def run(chunks: ClosingChunks, wfile: RecordingWfile, head_only: bool = False, **kwargs) -> None:
    write_stream(wfile, StreamResponse(200, HEADERS, chunks, **kwargs), head_only=head_only)


def test_the_head_has_no_content_length_closes_and_carries_the_security_headers() -> None:
    wfile = RecordingWfile()
    run(ClosingChunks([]), wfile)
    parsed = parse_response(wfile.written())
    assert parsed.status == 200
    assert "content-length" not in parsed.headers
    assert parsed.headers["connection"] == ["close"]
    assert parsed.one("Content-Type") == "text/event-stream"
    assert parsed.one("Cache-Control") == "no-store"
    for name, value in SECURITY_HEADERS.items():
        assert parsed.headers[name] == [value]


def test_no_store_false_leaves_cache_control_out() -> None:
    wfile = RecordingWfile()
    run(ClosingChunks([]), wfile, no_store=False)
    assert "cache-control" not in parse_response(wfile.written()).headers


def test_each_chunk_is_written_then_flushed_in_order_and_the_generator_is_closed() -> None:
    wfile = RecordingWfile()
    chunks = ClosingChunks([b"one", b"two", b"three"])
    run(chunks, wfile)
    kinds = [event for event in wfile.events if event != ("flush", b"")]
    assert [data for _, data in kinds[1:]] == [b"one", b"two", b"three"]
    after_head = wfile.events[2:]
    assert after_head == [("write", b"one"), ("flush", b""), ("write", b"two"), ("flush", b""), ("write", b"three"), ("flush", b"")]
    assert parse_response(wfile.written()).body == b"onetwothree"
    assert chunks.closed


@pytest.mark.parametrize(
    "error", [BrokenPipeError(), ConnectionResetError(), TimeoutError("timed out")], ids=["pipe", "reset", "timeout"]
)
def test_a_failed_write_ends_the_response_quietly_and_closes_the_generator(error: BaseException) -> None:
    wfile = RecordingWfile(fail_on_write=3, error=error)
    chunks = ClosingChunks([b"one", b"two", b"three"])
    run(chunks, wfile)
    assert chunks.closed
    assert wfile.written().endswith(b"one")


def test_an_exception_from_the_generator_ends_the_response_quietly_and_closes_it() -> None:
    wfile = RecordingWfile()
    chunks = ClosingChunks([b"one"], raises=RuntimeError("secret detail"))
    run(chunks, wfile)
    assert chunks.closed
    assert wfile.written().endswith(b"one")
    assert b"secret" not in wfile.written()


def test_head_writes_the_head_only_and_closes_the_unstarted_generator() -> None:
    wfile = RecordingWfile()
    chunks = ClosingChunks([b"one"])
    run(chunks, wfile, head_only=True)
    assert not chunks.started
    assert chunks.closed
    assert parse_response(wfile.written()).body == b""


def test_a_bodyless_status_writes_a_head_with_no_length_type_or_body() -> None:
    wfile = RecordingWfile()
    write_stream(wfile, StreamResponse(204, (), iter(())))
    parsed = parse_response(wfile.written())
    assert parsed.status == 204
    assert "content-length" not in parsed.headers
    assert "content-type" not in parsed.headers
    assert parsed.body == b""
