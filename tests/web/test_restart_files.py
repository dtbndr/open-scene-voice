import os
import stat
from pathlib import Path

import pytest
from restart_helper import FIXED, WAV_NAMES, bystanders, old_generation, snapshot

from scenevoice.web.discard_set_aside import discard_set_aside
from scenevoice.web.file_ops import REAL_OPS, FileOps
from scenevoice.web.not_ordinary import NotOrdinary
from scenevoice.web.restart_hook import restart_hook
from scenevoice.web.restart_messages import ROLLBACK_FAILED, SPARE_COPIES
from scenevoice.web.restore_set_aside import restore_set_aside
from scenevoice.web.scan_backups import scan_backups
from scenevoice.web.set_aside import SetAsideFailed
from scenevoice.web.set_aside_files import set_aside_files


@pytest.fixture
def project(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    return directory


def start_again(project, ops=REAL_OPS):
    old = old_generation(project)
    aside = set_aside_files(project, None, token="aa")
    return old, restart_hook(aside, project, None, ops)


def run_wrote(project, *, record=False, wavs=("001.wav",)):
    """What a doomed run leaves behind: new WAVs, and optionally the new record."""
    for name in wavs:
        (project / "audio" / name).write_bytes(b"NEW " + name.encode())
    if record:
        (project / "synth_record.json").write_bytes(b"NEW record")


def failing_on(call, real):
    count = [0]

    def wrapped(*args):
        count[0] += 1
        if count[0] == call:
            raise OSError("no")
        return real(*args)

    return wrapped


@pytest.mark.parametrize("outcome", ["done", "failed", "cancelled"])
def test_the_commit_is_the_first_done_scene_then_the_new_generation_stands_and_the_backups_go(project, outcome):
    old, hook = start_again(project)
    run_wrote(project, record=True)
    (project / ".write-restart-deadbeef-001.wav.tmp").write_bytes(b"kept from an earlier failure")
    assert hook(outcome, 1) == (None, None)
    assert snapshot(project) == {
        "audio/001.wav": b"NEW 001.wav",
        "synth_record.json": b"NEW record",
        ".write-restart-deadbeef-001.wav.tmp": b"kept from an earlier failure",
    }


def test_a_done_job_commits_even_if_no_scene_was_counted(project):
    old, hook = start_again(project)
    run_wrote(project)
    assert hook("done", 0) == (None, None)
    assert not scan_backups(project) and (project / "audio" / "001.wav").read_bytes() == b"NEW 001.wav"


@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
def test_without_a_done_scene_the_whole_old_generation_comes_back_and_nothing_new_stays(project, outcome):
    old, hook = start_again(project)
    run_wrote(project, wavs=("001.wav", "003.wav"), record=True)
    (project / ".write-restart-deadbeef-001.wav.tmp").write_bytes(b"kept from an earlier failure")
    assert hook(outcome, 0) == (None, None)
    assert snapshot(project) == {**old, ".write-restart-deadbeef-001.wav.tmp": b"kept from an earlier failure"}


def test_a_failure_before_any_file_is_written_restores_everything(project):
    old, hook = start_again(project)
    assert hook("failed", 0) == (None, None)
    assert snapshot(project) == old and not scan_backups(project)


def test_a_new_output_that_is_not_an_ordinary_file_fails_the_rollback_and_keeps_every_backup(project):
    old, hook = start_again(project)
    (project / "synth_record.json").mkdir()
    message, notice = hook("failed", 0)
    assert (message, notice) == (ROLLBACK_FAILED, None)
    assert sorted(p.name for p in project.glob(".write-restart-aa-*")) == sorted(f".write-restart-aa-{n}.tmp" for n in FIXED)
    assert sorted(p.name for p in (project / "audio").glob(".write-restart-aa-*")) == [f".write-restart-aa-{n}.tmp" for n in WAV_NAMES]


@pytest.mark.parametrize("phase", ["unlink-of-new-output", "copy", "replace"])
def test_a_removal_copy_or_replace_failure_in_the_rollback_keeps_all_backups_and_says_so(project, phase):
    real = FileOps()
    ops = FileOps(
        unlink=failing_on(1, real.unlink) if phase == "unlink-of-new-output" else real.unlink,
        copy=failing_on(2, real.copy) if phase == "copy" else real.copy,
        replace=failing_on(2, real.replace) if phase == "replace" else real.replace,
    )
    old, hook = start_again(project, ops)
    run_wrote(project, record=True)
    assert hook("cancelled", 0) == (ROLLBACK_FAILED, None)
    backups = sorted(str(p.relative_to(project)) for p in project.rglob(".write-restart-aa-*"))
    assert len(backups) == len(old)
    assert not list(project.rglob(".write-restore-*"))
    assert scan_backups(project)


def test_a_failed_unlink_of_a_backup_after_a_put_back_is_a_notice_not_a_failure(project):
    old, hook = start_again(project, FileOps(unlink=lambda path: (_ for _ in ()).throw(OSError("no")) if ".write-restart-" in path.name else os.unlink(path)))
    message, notice = hook("failed", 0)
    assert message is None and notice == SPARE_COPIES
    assert SPARE_COPIES == (
        "Your earlier audio is back. Spare copies of it remain in this project folder in files that start with "
        ".write-restart. Leave them where they are."
    )
    assert "delete" not in SPARE_COPIES.lower()
    assert {k: v for k, v in snapshot(project).items() if ".write-restart-" not in k} == old
    assert scan_backups(project)


def test_an_earlier_kept_recovery_set_coexists_with_a_later_attempts_spares_and_nothing_is_swept(project):
    old_generation(project)
    earlier = project / "audio" / ".write-restart-0f0f-001.wav.tmp"
    earlier.write_bytes(b"recovery set")
    aside = set_aside_files(project, None, token="bb")
    spare_ops = FileOps(unlink=lambda path: (_ for _ in ()).throw(OSError("no")) if "-bb-" in path.name else os.unlink(path))
    assert restart_hook(aside, project, None, spare_ops)("failed", 0) == (None, SPARE_COPIES)
    assert earlier.read_bytes() == b"recovery set" and scan_backups(project)


@pytest.fixture
def project_set_aside_files(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    return directory


def names(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file())


def failing_on_set_aside_files(call: int, real):
    """A wrapper that raises on its `call`-th use (1-based) and otherwise does the real thing."""
    count = [0]

    def wrapped(*args):
        count[0] += 1
        if count[0] == call:
            raise OSError("no")
        return real(*args)

    return wrapped


# --- set_aside_files -------------------------------------------------------------------------------------------------


def test_each_allowlisted_file_is_renamed_in_its_own_directory_to_a_write_restart_name(project_set_aside_files):
    old = old_generation(project_set_aside_files)
    keep = bystanders(project_set_aside_files)
    aside = set_aside_files(project_set_aside_files, None, token="abc123")
    assert len(aside.moves) == len(old)
    for original, backup in aside.moves:
        assert backup.parent == original.parent
        assert backup.name == f".write-restart-abc123-{original.name}.tmp"
        assert not original.exists()
        assert backup.read_bytes() == old[str(original.relative_to(project_set_aside_files))]
    assert {k: v for k, v in snapshot(project_set_aside_files).items() if not k.endswith(".tmp") or k in keep} == keep
    assert scan_backups(project_set_aside_files)


def test_the_token_is_random_per_attempt_when_not_given(project_set_aside_files):
    old_generation(project_set_aside_files)
    first = set_aside_files(project_set_aside_files, None)
    for original, backup in first.moves:
        backup.rename(original)
    second = set_aside_files(project_set_aside_files, None)
    assert first.moves[0][1] != second.moves[0][1]


def test_a_file_that_is_not_ordinary_refuses_the_whole_set_aside_before_any_rename(project_set_aside_files, tmp_path):
    old_generation(project_set_aside_files)
    (project_set_aside_files / "scene_manifest.csv").unlink()
    (project_set_aside_files / "scene_manifest.csv").symlink_to(tmp_path / "nowhere")
    before = names(project_set_aside_files)
    with pytest.raises(NotOrdinary):
        set_aside_files(project_set_aside_files, None)
    assert names(project_set_aside_files) == before and not scan_backups(project_set_aside_files)


def test_a_rename_that_fails_after_k_of_n_raises_with_the_k_that_happened(project_set_aside_files):
    old_generation(project_set_aside_files)
    ops = FileOps(rename=failing_on_set_aside_files(3, os.rename))
    with pytest.raises(SetAsideFailed) as caught:
        set_aside_files(project_set_aside_files, None, ops)
    assert [original.name for original, _ in caught.value.done.moves] == list(FIXED[:2])


# --- restore_set_aside: the three-phase copy restore -----------------------------------------------------------------


def aside_all(project_set_aside_files, ops=REAL_OPS):
    old = old_generation(project_set_aside_files)
    return old, set_aside_files(project_set_aside_files, None, ops, token="aa")


def temps(project_set_aside_files) -> list[str]:
    return [n for n in names(project_set_aside_files) if ".write-restore-" in n]


def test_a_restore_puts_every_file_back_byte_for_byte_with_one_link_and_removes_the_backups(project_set_aside_files):
    old, aside = aside_all(project_set_aside_files)
    assert restore_set_aside(aside) == "restored"
    assert snapshot(project_set_aside_files) == old
    assert all(os.lstat(original).st_nlink == 1 and stat.S_ISREG(os.lstat(original).st_mode) for original, _ in aside.moves)
    assert not scan_backups(project_set_aside_files) and temps(project_set_aside_files) == []


@pytest.mark.parametrize("phase", ["copy", "replace"])
@pytest.mark.parametrize("call", [1, 2, 3])
def test_a_copy_or_replace_failure_keeps_every_backup_and_leaves_no_restore_temp(project_set_aside_files, phase, call):
    old, aside = aside_all(project_set_aside_files)
    ops = FileOps(**{phase: failing_on_set_aside_files(call, getattr(FileOps(), phase))})
    assert restore_set_aside(aside, ops) == "failed"
    assert temps(project_set_aside_files) == []
    assert all(backup.read_bytes() == old[str(original.relative_to(project_set_aside_files))] for original, backup in aside.moves)
    restored = [original for original, _ in aside.moves if original.exists()]
    assert len(restored) == (call - 1 if phase == "replace" else 0)
    assert all(original.read_bytes() == old[str(original.relative_to(project_set_aside_files))] for original in restored)


def test_a_failed_unlink_of_the_backups_is_spares_the_audio_is_back_and_the_strays_stay(project_set_aside_files):
    old, aside = aside_all(project_set_aside_files)
    assert restore_set_aside(aside, FileOps(unlink=failing_on_set_aside_files(2, os.unlink))) == "spares"
    assert snapshot(project_set_aside_files).keys() >= old.keys()
    assert all(original.read_bytes() == old[str(original.relative_to(project_set_aside_files))] for original, _ in aside.moves)
    assert len([b for _, b in aside.moves if b.exists()]) == 1


def test_a_restore_never_touches_a_backup_it_did_not_make(project_set_aside_files):
    old_generation(project_set_aside_files)
    earlier = project_set_aside_files / "audio" / ".write-restart-deadbeef-001.wav.tmp"
    earlier.write_bytes(b"from an earlier failed rollback")
    aside = set_aside_files(project_set_aside_files, None, token="aa")
    assert restore_set_aside(aside) == "restored"
    assert earlier.read_bytes() == b"from an earlier failed rollback"


# --- discard_set_aside ----------------------------------------------------------------------------------------------


def test_a_discard_removes_exactly_this_attempts_backups(project_set_aside_files):
    old, aside = aside_all(project_set_aside_files)
    earlier = project_set_aside_files / ".write-restart-deadbeef-synth_record.json.tmp"
    earlier.write_bytes(b"earlier")
    discard_set_aside(aside)
    assert names(project_set_aside_files) == [".write-restart-deadbeef-synth_record.json.tmp"]


def test_a_discard_that_cannot_unlink_leaves_the_rest_in_place_and_raises_nothing(project_set_aside_files):
    old, aside = aside_all(project_set_aside_files)
    discard_set_aside(aside, FileOps(unlink=failing_on_set_aside_files(1, os.unlink)))
    assert len([b for _, b in aside.moves if b.exists()]) == 1


def test_a_copy_that_dies_half_way_leaves_no_partial_restore_temp(project_set_aside_files):
    old, aside = aside_all(project_set_aside_files)

    def half_written(source, target):
        target.write_bytes(b"half")
        raise OSError("disk full")

    assert restore_set_aside(aside, FileOps(copy=half_written)) == "failed"
    assert temps(project_set_aside_files) == []
