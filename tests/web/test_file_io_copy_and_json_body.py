import json
import os
import stat
import sys
from io import BytesIO

import pytest
from web_http_helper import make_request

from scenevoice.web import (
    JsonBody,
    Request,
    Response,
    WorkspaceError,
    make_launch_dir,
    read_json_body,
    remove_launch_dir,
    write_file_atomic,
    write_private_file,
)
from scenevoice.web.copy_file import copy_file


def test_the_bytes_are_copied_to_a_new_file_with_an_ordinary_mode_and_one_link(tmp_path):
    source = tmp_path / "a"
    source.write_bytes(b"x" * (3 << 20))
    copy_file(source, tmp_path / "b")
    status = os.lstat(tmp_path / "b")
    assert (tmp_path / "b").read_bytes() == source.read_bytes() and status.st_nlink == 1
    assert status.st_mode & 0o777 == 0o666 & ~_umask()


def _umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current


def test_an_existing_target_or_a_symlink_target_is_never_written_through(tmp_path):
    source = tmp_path / "a"
    source.write_bytes(b"new")
    existing = tmp_path / "b"
    existing.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        copy_file(source, existing)
    victim = tmp_path / "victim"
    victim.write_bytes(b"victim")
    (tmp_path / "c").symlink_to(victim)
    with pytest.raises(OSError):
        copy_file(source, tmp_path / "c")
    assert existing.read_bytes() == b"old" and victim.read_bytes() == b"victim"


def test_writes_exact_bytes_with_the_umask_derived_mode(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.write_file_atomic"]
    monkeypatch.setattr(module, "_UMASK", 0o027)
    data = b"\xef\xbb\xbfline\r\nno newline"
    write_file_atomic(tmp_path, "script.md", data)
    assert (tmp_path / "script.md").read_bytes() == data
    assert stat.S_IMODE(os.stat(tmp_path / "script.md").st_mode) == 0o666 & ~0o027
    assert os.listdir(tmp_path) == ["script.md"]


def test_temp_file_lives_in_the_directory_with_the_write_pattern(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.write_file_atomic"]
    seen: list[str] = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(os.path.basename(src))
        assert os.path.dirname(src) == str(tmp_path)
        real_replace(src, dst)

    monkeypatch.setattr(module.os, "replace", spy)
    write_file_atomic(tmp_path, "script.md", b"x")
    assert len(seen) == 1
    assert seen[0].startswith(".write-") and seen[0].endswith(".tmp")


def test_failed_write_keeps_the_old_file_and_removes_the_temp(tmp_path, monkeypatch):
    (tmp_path / "script.md").write_bytes(b"old")
    module = sys.modules["scenevoice.web.write_file_atomic"]
    calls: list[str] = []

    def boom(src, dst):
        calls.append("replace")
        raise OSError("disk full")

    monkeypatch.setattr(module.os, "replace", boom)
    with pytest.raises(OSError):
        write_file_atomic(tmp_path, "script.md", b"new")
    assert calls == ["replace"]
    assert (tmp_path / "script.md").read_bytes() == b"old"
    assert os.listdir(tmp_path) == ["script.md"]


@pytest.mark.parametrize("name", ["a/b", "../x", "", ".hidden", "a\\b", "a\x00b", "/abs"])
def test_non_plain_names_are_refused(tmp_path, name):
    with pytest.raises(ValueError):
        write_file_atomic(tmp_path, name, b"x")
    assert os.listdir(tmp_path) == []


def test_target_that_is_the_key_file_is_refused_and_left_untouched(tmp_path):
    (tmp_path / "keys.env").write_bytes(b"K=1")
    with pytest.raises(WorkspaceError):
        write_file_atomic(tmp_path, "keys.env", b"new", key_file=tmp_path / "keys.env")
    assert (tmp_path / "keys.env").read_bytes() == b"K=1"
    write_file_atomic(tmp_path, "other", b"ok", key_file=tmp_path / "keys.env")
    assert (tmp_path / "other").read_bytes() == b"ok"


def test_target_with_two_hard_links_is_refused_and_the_linked_file_untouched(tmp_path):
    (tmp_path / "script.md").write_bytes(b"old")
    os.link(tmp_path / "script.md", tmp_path / "linked")
    with pytest.raises(WorkspaceError):
        write_file_atomic(tmp_path, "script.md", b"new")
    with pytest.raises(WorkspaceError):
        write_file_atomic(tmp_path, "script.md", b"new", key_file=None)
    assert (tmp_path / "linked").read_bytes() == b"old"
    assert (tmp_path / "script.md").read_bytes() == b"old"


def test_missing_target_is_created(tmp_path):
    write_file_atomic(tmp_path, "new.md", b"x", key_file=tmp_path / "keys.env")
    assert (tmp_path / "new.md").read_bytes() == b"x"


def test_the_exact_bytes_land_in_a_new_0600_file_in_the_directory(tmp_path):
    data = "café\r\n{}\x00".encode()
    path = write_private_file(tmp_path, "plan-", ".json", data)
    assert path.parent == tmp_path and path.name.startswith("plan-") and path.name.endswith(".json")
    assert path.read_bytes() == data
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_two_files_never_share_a_name(tmp_path):
    assert write_private_file(tmp_path, "p-", ".json", b"a") != write_private_file(tmp_path, "p-", ".json", b"b")


def test_launch_dir_is_private_empty_and_unique():
    first, second = make_launch_dir(), make_launch_dir()
    try:
        assert first != second
        assert first.is_dir() and list(first.iterdir()) == []
        assert stat.S_IMODE(os.stat(first).st_mode) == 0o700
    finally:
        remove_launch_dir(first)
        remove_launch_dir(second)


def test_removal_deletes_contents_and_tolerates_a_missing_directory():
    path = make_launch_dir()
    (path / "f.txt").write_text("x", encoding="utf-8")
    remove_launch_dir(path)
    assert not path.exists()
    remove_launch_dir(path)


JSON = ("content-type", "application/json")


def post(body: bytes, *extra: tuple[str, str], length: str | None = None, method: str = "POST") -> Request:
    length = str(len(body)) if length is None else length
    return make_request(method, headers=[JSON, ("content-length", length), *extra], body=body)


def kind_and_status(result: object) -> tuple[str, int]:
    assert isinstance(result, Response)
    return json.loads(result.body)["error"]["kind"], result.status


def test_valid_json_is_parsed_and_the_read_asks_for_exactly_content_length() -> None:
    asked: list[int] = []

    def read(n: int) -> bytes:
        asked.append(n)
        return b'{"a": 1}'

    request = Request("POST", "/x", headers=(JSON, ("content-length", "8")), read_body=read)
    assert read_json_body(request) == JsonBody({"a": 1})
    assert asked == [8]


def test_content_type_parameters_are_accepted() -> None:
    request = make_request("POST", headers=[("content-type", "application/json; charset=utf-8"), ("content-length", "2")], body=b"{}")
    assert read_json_body(request) == JsonBody({})


# Cross-origin: a plain HTML form can only send these types, so they never reach a handler.
@pytest.mark.parametrize("content_type", [None, "text/plain", "application/x-www-form-urlencoded"])
def test_other_content_types_are_415(content_type: str | None) -> None:
    headers = [("content-length", "2")] + ([("content-type", content_type)] if content_type else [])
    assert kind_and_status(read_json_body(make_request("POST", headers=headers, body=b"{}"))) == ("bad_request", 415)


@pytest.mark.parametrize("length", [None, "-1", "5.0"])
def test_a_content_length_that_is_not_plain_ascii_digits_is_400(length: str | None) -> None:
    headers = [JSON] + ([("content-length", length)] if length is not None else [])
    request = make_request("POST", headers=headers, body=b"12345")
    assert kind_and_status(read_json_body(request)) == ("bad_request", 400)


def test_any_transfer_encoding_is_400() -> None:
    request = post(b"{}", ("transfer-encoding", "chunked"))
    assert kind_and_status(read_json_body(request)) == ("bad_request", 400)


def test_a_bodyless_method_refuses_a_body_and_allows_none_or_zero() -> None:
    assert kind_and_status(read_json_body(post(b"{}", method="GET"))) == ("bad_request", 400)
    assert read_json_body(make_request("GET", headers=[])) == JsonBody(None)


def test_over_the_cap_is_413_decided_before_any_read() -> None:
    def never(n: int) -> bytes:
        raise AssertionError("read before the size check")

    request = Request("POST", "/x", headers=(JSON, ("content-length", "65537")), read_body=never)
    assert kind_and_status(read_json_body(request)) == ("bad_request", 413)


@pytest.mark.parametrize("body", [b"{", b'"\\ud800"'])
def test_invalid_json_and_lone_surrogates_are_400(body: bytes) -> None:
    assert kind_and_status(read_json_body(post(body))) == ("bad_request", 400)


def test_a_short_read_is_400() -> None:
    request = Request("POST", "/x", headers=(JSON, ("content-length", "10")), read_body=lambda n: BytesIO(b"{}").read(n))
    assert kind_and_status(read_json_body(request)) == ("bad_request", 400)
