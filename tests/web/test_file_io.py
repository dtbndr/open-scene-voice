import json
import os
import sys
import threading

import pytest

from scenevoice.web import (
    FileTooLargeError,
    JsonRead,
    open_regular_file,
    read_json_file,
    read_regular_bytes,
    regular_file,
)

CAP = 64


def read(directory, name="f.json", key_file=None):
    return read_json_file(directory, name, CAP, key_file)


def test_an_absent_entry_is_none_and_a_plain_file_is_parsed(tmp_path):
    assert read(tmp_path) == JsonRead("none")
    (tmp_path / "f.json").write_text(json.dumps({"a": [1, "\u00e9"]}, ensure_ascii=False), encoding="utf-8")
    assert read(tmp_path) == JsonRead("ok", {"a": [1, "\u00e9"]})


def test_a_file_at_the_cap_is_read_and_one_byte_over_is_unreadable(tmp_path):
    (tmp_path / "f.json").write_text('"' + "a" * (CAP - 2) + '"')
    assert read(tmp_path).state == "ok"
    (tmp_path / "f.json").write_text('"' + "a" * (CAP - 1) + '"')
    assert read(tmp_path) == JsonRead("unreadable")


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"{", id="truncated"),
        pytest.param(b"", id="empty"),
        pytest.param(b"\xff\xfe{}", id="not-utf8"),
        pytest.param(b"NaN extra", id="trailing-text"),
        pytest.param(b"[" * 100000 + b"]" * 100000, id="deeply-nested"),
    ],
)
def test_malformed_undecodable_or_deeply_nested_content_is_unreadable_never_an_error(tmp_path, content):
    (tmp_path / "f.json").write_bytes(content)
    assert read_json_file(tmp_path, "f.json", 1_000_000, None) == JsonRead("unreadable")


def test_a_symlink_a_second_hard_link_a_directory_and_the_key_file_are_unreadable(tmp_path):
    (tmp_path / "real").write_text("{}")
    os.symlink(tmp_path / "real", tmp_path / "link.json")
    os.link(tmp_path / "real", tmp_path / "twin.json")
    (tmp_path / "dir.json").mkdir()
    (tmp_path / "key.json").write_text("{}")
    assert [read(tmp_path, name) for name in ("link.json", "twin.json", "dir.json")] == [JsonRead("unreadable")] * 3
    assert read(tmp_path, "key.json", key_file=tmp_path / "key.json") == JsonRead("unreadable")
    assert read(tmp_path, "key.json") == JsonRead("ok", {})  # positive control: only the key-file rule refused it


def test_the_cap_is_a_parameter_of_the_one_reader(tmp_path):
    (tmp_path / "f.json").write_text("[" + "1," * 40 + "1]")
    assert read_json_file(tmp_path, "f.json", 1000, None).state == "ok"
    assert read(tmp_path).state == "unreadable"


def test_reads_exact_bytes_up_to_the_cap(tmp_path):
    (tmp_path / "f").write_bytes(b"ab\r\n\xef\xbb\xbf")
    assert read_regular_bytes(tmp_path / "f", 7) == b"ab\r\n\xef\xbb\xbf"
    (tmp_path / "empty").write_bytes(b"")
    assert read_regular_bytes(tmp_path / "empty", 5) == b""


def test_over_cap_raises_the_distinct_error(tmp_path):
    (tmp_path / "f").write_bytes(b"x" * 6)
    with pytest.raises(FileTooLargeError):
        read_regular_bytes(tmp_path / "f", 5)


def test_symlink_missing_and_directory_return_none(tmp_path):
    (tmp_path / "real").write_bytes(b"x")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    (tmp_path / "d").mkdir()
    assert read_regular_bytes(tmp_path / "link", 10) is None
    assert read_regular_bytes(tmp_path / "absent", 10) is None
    assert read_regular_bytes(tmp_path / "d", 10) is None


def test_fifo_never_blocks_and_returns_none(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    result: list[object] = []
    worker = threading.Thread(target=lambda: result.append(read_regular_bytes(tmp_path / "pipe", 10)), daemon=True)
    worker.start()
    worker.join(5)
    assert result == [None]


def test_key_file_descriptor_is_refused_but_other_files_are_read(tmp_path):
    (tmp_path / "keys.env").write_bytes(b"K=1")
    (tmp_path / "other").write_bytes(b"x")
    assert read_regular_bytes(tmp_path / "keys.env", 10, key_file=tmp_path / "keys.env") is None
    assert read_regular_bytes(tmp_path / "other", 10, key_file=tmp_path / "keys.env") == b"x"


def test_file_with_two_hard_links_is_refused(tmp_path):
    (tmp_path / "f").write_bytes(b"x")
    os.link(tmp_path / "f", tmp_path / "g")
    assert read_regular_bytes(tmp_path / "f", 10) is None
    assert read_regular_bytes(tmp_path / "f", 10, key_file=None) is None


def test_regular_file_returns_its_path_through_a_real_directory(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "01.wav").write_bytes(b"x")
    (tmp_path / "script.md").write_text("x")
    assert regular_file(tmp_path, "script.md") == tmp_path / "script.md"
    assert regular_file(tmp_path, "audio", "01.wav") == tmp_path / "audio" / "01.wav"


def test_symlink_directory_fifo_and_missing_are_refused(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "01.wav").write_bytes(b"x")
    (tmp_path / "audio").symlink_to(elsewhere)
    (tmp_path / "real.md").write_text("x")
    (tmp_path / "script.md").symlink_to(tmp_path / "real.md")
    (tmp_path / "adir").mkdir()
    os.mkfifo(tmp_path / "pipe")
    assert regular_file(tmp_path, "audio", "01.wav") is None
    assert regular_file(tmp_path, "script.md") is None
    assert regular_file(tmp_path, "adir") is None
    assert regular_file(tmp_path, "pipe") is None
    assert regular_file(tmp_path, "absent") is None


def test_part_that_is_not_an_exact_entry_is_refused_before_lstat(tmp_path, fake_listing, monkeypatch):
    import sys

    asked = fake_listing("regular_file", ["Script.md", "audio"])
    calls: list[str] = []
    module = sys.modules["scenevoice.web.regular_file"]
    monkeypatch.setattr(module.os, "lstat", lambda p, **k: calls.append("lstat") or None)
    assert regular_file(tmp_path, "script.md") is None
    assert regular_file(tmp_path, "Audio", "01.wav") is None
    assert asked  # positive control
    assert calls == []


def test_key_file_itself_is_refused_and_another_file_is_not(tmp_path):
    (tmp_path / "keys.env").write_text("K=1")
    (tmp_path / "other").write_text("x")
    assert regular_file(tmp_path, "keys.env", key_file=tmp_path / "keys.env") is None
    assert regular_file(tmp_path, "other", key_file=tmp_path / "keys.env") == tmp_path / "other"


def test_file_with_two_hard_links_is_refused_with_or_without_a_key_file(tmp_path):
    (tmp_path / "script.md").write_text("x")
    os.link(tmp_path / "script.md", tmp_path / "elsewhere-name")
    assert regular_file(tmp_path, "script.md") is None
    assert regular_file(tmp_path, "script.md", key_file=tmp_path / "nokey") is None


def opened_size(path, cap=10, key_file=None):
    found = open_regular_file(path, cap, key_file)
    if found is None:
        return None
    fd, size = found
    os.close(fd)
    return size


@pytest.fixture
def closed(monkeypatch):
    """Every descriptor the module closes (the real close still runs)."""
    module_os = sys.modules["scenevoice.web.open_regular_file"].os
    real, seen = module_os.close, []
    monkeypatch.setattr(module_os, "close", lambda fd: (seen.append(fd), real(fd))[1])
    return seen


def test_a_regular_file_gives_a_readable_descriptor_and_its_size(tmp_path):
    (tmp_path / "f").write_bytes(b"abcde")
    fd, size = open_regular_file(tmp_path / "f", 10, None)
    try:
        assert (size, os.read(fd, 10)) == (5, b"abcde")
    finally:
        os.close(fd)
    (tmp_path / "empty").write_bytes(b"")
    assert opened_size(tmp_path / "empty") == 0


def test_the_cap_boundary_allows_the_cap_and_refuses_one_more_byte_with_the_descriptor_closed(tmp_path, closed):
    (tmp_path / "ten").write_bytes(b"x" * 10)
    (tmp_path / "eleven").write_bytes(b"x" * 11)
    assert opened_size(tmp_path / "ten") == 10
    closed.clear()
    with pytest.raises(FileTooLargeError):
        open_regular_file(tmp_path / "eleven", 10, None)
    assert len(closed) == 1


def test_a_file_with_two_hard_links_is_refused_with_the_descriptor_closed(tmp_path, closed):
    (tmp_path / "f").write_bytes(b"x")
    assert opened_size(tmp_path / "f") == 1  # positive control
    os.link(tmp_path / "f", tmp_path / "g")
    closed.clear()
    assert open_regular_file(tmp_path / "f", 10, None) is None
    assert len(closed) == 1


def test_a_symlink_a_missing_file_and_a_directory_are_refused(tmp_path, closed):
    (tmp_path / "real").write_bytes(b"x")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    (tmp_path / "d").mkdir()
    assert opened_size(tmp_path / "real") == 1  # positive control
    closed.clear()
    assert open_regular_file(tmp_path / "link", 10, None) is None
    assert open_regular_file(tmp_path / "absent", 10, None) is None
    assert closed == []  # the symlink and the missing file never opened
    assert open_regular_file(tmp_path / "d", 10, None) is None
    assert len(closed) == 1  # the directory opened, then was closed


def test_a_fifo_never_blocks_and_is_refused_with_the_descriptor_closed(tmp_path, closed):
    os.mkfifo(tmp_path / "pipe")
    result: list[object] = []
    worker = threading.Thread(target=lambda: result.append(open_regular_file(tmp_path / "pipe", 10, None)), daemon=True)
    worker.start()
    worker.join(5)
    assert result == [None]
    assert len(closed) == 1


def test_the_key_file_inode_is_refused_through_the_descriptor_and_other_files_are_not(tmp_path, closed):
    (tmp_path / "keys.env").write_bytes(b"K=1")
    (tmp_path / "other").write_bytes(b"x")
    assert opened_size(tmp_path / "other", key_file=tmp_path / "keys.env") == 1
    closed.clear()
    assert open_regular_file(tmp_path / "keys.env", 10, tmp_path / "keys.env") is None
    assert len(closed) == 1


def test_an_oserror_from_fstat_is_a_refusal_with_the_descriptor_closed(tmp_path, closed, monkeypatch):
    (tmp_path / "f").write_bytes(b"x")
    module_os = sys.modules["scenevoice.web.open_regular_file"].os

    def broken(fd):
        raise OSError("gone")

    monkeypatch.setattr(module_os, "fstat", broken)
    assert open_regular_file(tmp_path / "f", 10, None) is None
    assert len(closed) == 1
