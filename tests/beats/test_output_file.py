import os
from pathlib import Path

from scenevoice.beats.check_out_path import check_out_path
from scenevoice.beats.write_out_file import write_out_file

COMMAND = "beats"
running_as_root = hasattr(os, "geteuid") and os.geteuid() == 0


def test_fresh_path_in_existing_directory_passes(tmp_path: Path) -> None:
    assert check_out_path(tmp_path / "out.txt", command=COMMAND) is None


def test_existing_file_fails_naming_the_path(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("x")
    message = check_out_path(target, command=COMMAND)
    assert message is not None and "already exists" in message and str(target) in message
    assert "\n" not in message


def test_symlink_fails_whether_dangling_or_not(tmp_path: Path) -> None:
    real = tmp_path / "real.txt"
    real.write_text("x")
    live = tmp_path / "live"
    live.symlink_to(real)
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "nowhere")
    for link in (live, dangling):
        message = check_out_path(link, command=COMMAND)
        assert message is not None and "already exists" in message and str(link) in message


def test_missing_parent_fails(tmp_path: Path) -> None:
    message = check_out_path(tmp_path / "missing" / "out.txt", command=COMMAND)
    assert message is not None and "directory" in message and "\n" not in message


def test_blank_or_separator_ended_name_names_no_file(tmp_path: Path) -> None:
    for name in ["", "   ", f"{tmp_path}/"]:
        assert check_out_path(name, command=COMMAND) == (
            f"--out {name!r} has no file name; give a path that ends in a file name"
        )


def test_write_exact_utf8_bytes_without_added_newline(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    assert write_out_file(target, "café — line", command=COMMAND) is None
    assert target.read_bytes() == "café — line".encode()


def test_write_refuses_existing_file_and_keeps_its_bytes(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_bytes(b"keep me")
    message = write_out_file(target, "new", command=COMMAND)
    assert message is not None and "already exists" in message and str(target) in message
    assert "\n" not in message
    assert target.read_bytes() == b"keep me"


def test_write_refuses_dangling_symlink(tmp_path: Path) -> None:
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "nowhere")
    message = write_out_file(link, "new", command=COMMAND)
    assert message is not None and "already exists" in message
    assert not (tmp_path / "nowhere").exists()


def test_failed_write_unlinks_the_file_it_created(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"

    def failing(descriptor: int, data: bytes) -> None:
        raise OSError(28, "No space left on device")

    message = write_out_file(target, "x", write_bytes=failing, command=COMMAND)
    assert message is not None and str(target) in message and "\n" not in message
    assert not os.path.lexists(target)


def test_cleanup_never_unlinks_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_bytes(b"keep me")
    calls: list[bytes] = []

    def recording(descriptor: int, data: bytes) -> None:
        calls.append(data)

    message = write_out_file(target, "new", write_bytes=recording, command=COMMAND)
    assert message is not None and "already exists" in message
    assert calls == []
    assert target.read_bytes() == b"keep me"

