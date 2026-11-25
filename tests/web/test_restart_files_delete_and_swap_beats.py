import os
import sys
from pathlib import Path

import pytest
from beats_sidecar_helper import (
    OLD,
    REVISION,
    put_candidate,
    put_old_beats,
    sidecar_bytes,
)
from restart_helper import FIXED, bystanders, old_generation, snapshot

from scenevoice.web import beats_hook, swap_beats
from scenevoice.web.beats_messages import BEATS_UNREADABLE, COULD_NOT_FINISH
from scenevoice.web.delete_exact_files import delete_exact_files
from scenevoice.web.file_ops import FileOps
from scenevoice.web.job_availability import BEATS_EXIST
from scenevoice.web.not_ordinary import NotOrdinary


@pytest.fixture
def project(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    return directory


def test_only_the_exact_allowlisted_names_are_removed_and_every_other_file_stays(project):
    old_generation(project)
    kept = bystanders(project)
    delete_exact_files(project, None)
    assert snapshot(project) == kept


@pytest.mark.parametrize("name", ["audio/001.wav"])
@pytest.mark.parametrize("shape", ["symlink", "hard-link"])  # write/delete outside the project
def test_an_allowlisted_name_that_is_not_an_ordinary_file_refuses_everything_and_deletes_nothing(project, tmp_path, name, shape):
    old_generation(project)
    target = project / name
    target.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    if shape == "symlink":
        target.symlink_to(outside)
    else:
        os.link(outside, target)
    before = sorted(str(p.relative_to(project)) for p in project.rglob("*"))
    with pytest.raises(NotOrdinary):
        delete_exact_files(project, None)
    assert sorted(str(p.relative_to(project)) for p in project.rglob("*")) == before
    assert outside.read_bytes() == b"outside"


def test_the_key_file_is_never_deleted_even_under_an_allowlisted_name(project):
    old_generation(project)
    key = project / "line_timings.json"
    with pytest.raises(NotOrdinary):
        delete_exact_files(project, key)
    assert key.exists() and (project / "audio" / "001.wav").exists()


@pytest.mark.parametrize("shape", ["symlink", "file"])
def test_an_audio_entry_that_is_not_a_real_directory_refuses_everything(project, tmp_path, shape):
    old_generation(project)
    for child in (project / "audio").iterdir():
        child.unlink()
    (project / "audio").rmdir()
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "001.wav").write_bytes(b"elsewhere")
    if shape == "symlink":
        (project / "audio").symlink_to(real)
    else:
        (project / "audio").write_bytes(b"not a folder")
    with pytest.raises(NotOrdinary):
        delete_exact_files(project, None)
    assert (project / "synth_record.json").exists() and (real / "001.wav").read_bytes() == b"elsewhere"


PACK = ("scene_manifest.csv", "resolve_timeline.otio")


@pytest.fixture
def project_delete_pack_outputs(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    return directory


def test_pack_only_removes_the_manifest_and_the_timeline_and_leaves_the_record_the_line_markers_the_audio_and_the_rest(project_delete_pack_outputs):
    old = old_generation(project_delete_pack_outputs)
    kept = bystanders(project_delete_pack_outputs)
    delete_exact_files(project_delete_pack_outputs, None, pack_only=True)
    assert snapshot(project_delete_pack_outputs) == {**{k: v for k, v in old.items() if k not in PACK}, **kept}


def test_pack_only_with_nothing_to_delete_is_fine(project_delete_pack_outputs):
    (project_delete_pack_outputs / "synth_record.json").write_bytes(b"{}")
    delete_exact_files(project_delete_pack_outputs, None, pack_only=True)
    assert (project_delete_pack_outputs / "synth_record.json").exists()


@pytest.mark.parametrize("name", PACK)
@pytest.mark.parametrize("shape", ["symlink", "directory", "hard-link"])
def test_a_pack_output_that_is_not_an_ordinary_file_refuses_and_deletes_nothing(project_delete_pack_outputs, tmp_path, name, shape):
    old_generation(project_delete_pack_outputs)
    target = project_delete_pack_outputs / name
    target.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    if shape == "symlink":
        target.symlink_to(outside)
    elif shape == "directory":
        target.mkdir()
    else:
        os.link(outside, target)
    before = sorted(str(p.relative_to(project_delete_pack_outputs)) for p in project_delete_pack_outputs.rglob("*"))
    with pytest.raises(NotOrdinary):
        delete_exact_files(project_delete_pack_outputs, None, pack_only=True)
    assert sorted(str(p.relative_to(project_delete_pack_outputs)) for p in project_delete_pack_outputs.rglob("*")) == before
    assert outside.read_bytes() == b"outside"


def test_pack_only_judges_the_pack_outputs_alone_a_linked_wav_or_audio_symlink_does_not_refuse_it(project_delete_pack_outputs, tmp_path):
    old_generation(project_delete_pack_outputs)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (project_delete_pack_outputs / "line_timings.json").unlink()
    (project_delete_pack_outputs / "line_timings.json").symlink_to(elsewhere)
    os.link(project_delete_pack_outputs / "audio" / "001.wav", elsewhere / "linked.wav")
    delete_exact_files(project_delete_pack_outputs, None, pack_only=True)
    assert not (project_delete_pack_outputs / "scene_manifest.csv").exists() and (project_delete_pack_outputs / "audio" / "001.wav").exists()


def test_the_key_file_is_never_deleted_under_a_pack_output_name(project_delete_pack_outputs):
    old_generation(project_delete_pack_outputs)
    with pytest.raises(NotOrdinary):
        delete_exact_files(project_delete_pack_outputs, project_delete_pack_outputs / "resolve_timeline.otio", pack_only=True)
    assert (project_delete_pack_outputs / "resolve_timeline.otio").exists() and (project_delete_pack_outputs / "scene_manifest.csv").exists()


def test_an_oserror_is_raised_not_swallowed(project_delete_pack_outputs):
    old_generation(project_delete_pack_outputs)

    def failing(path: Path) -> None:
        raise OSError("disk says no")

    with pytest.raises(OSError, match="disk says no"):
        delete_exact_files(project_delete_pack_outputs, None, FileOps(unlink=failing), pack_only=True)


def test_a_finished_job_swaps_a_redo_in_and_leaves_no_candidate(tmp_path):
    put_old_beats(tmp_path)
    candidate = put_candidate(tmp_path)
    assert beats_hook(tmp_path, candidate, REVISION, True, None)("done", 0) == (None, None)
    assert os.listdir(tmp_path) == ["beats.json"] and (tmp_path / "beats.json").read_bytes() == sidecar_bytes()


def test_a_finished_first_run_links_beats_json_and_removes_the_candidate(tmp_path):
    candidate = put_candidate(tmp_path)
    assert beats_hook(tmp_path, candidate, REVISION, False, None)("done", 0) == (None, None)
    assert os.listdir(tmp_path) == ["beats.json"] and os.stat(tmp_path / "beats.json").st_nlink == 1


def test_a_finished_job_whose_answer_fails_the_check_fails_with_the_unreadable_message_and_deletes_the_candidate(tmp_path):
    put_old_beats(tmp_path)
    candidate = put_candidate(tmp_path, sidecar_bytes("0" * 64))
    assert beats_hook(tmp_path, candidate, REVISION, True, None)("done", 0) == (BEATS_UNREADABLE, None)
    assert os.listdir(tmp_path) == ["beats.json"] and (tmp_path / "beats.json").read_bytes() == OLD


def test_a_first_run_that_finds_beats_json_made_meanwhile_fails_and_deletes_the_candidate_without_touching_the_file(tmp_path):
    candidate = put_candidate(tmp_path)
    put_old_beats(tmp_path)
    assert beats_hook(tmp_path, candidate, REVISION, False, None)("done", 0) == (BEATS_EXIST, None)
    assert os.listdir(tmp_path) == ["beats.json"] and (tmp_path / "beats.json").read_bytes() == OLD


PARTIAL = sidecar_bytes()[:25]


@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
@pytest.mark.parametrize("content", [PARTIAL, sidecar_bytes(), b""], ids=["half-a-document", "a-valid-sidecar", "empty"])
@pytest.mark.parametrize("redo", [True, False])
def test_a_failed_or_cancelled_job_never_swaps_and_always_deletes_the_candidate_even_a_complete_one(tmp_path, outcome, content, redo):
    old = put_old_beats(tmp_path) if redo else None
    candidate = put_candidate(tmp_path, content)
    assert beats_hook(tmp_path, candidate, REVISION, redo, None)(outcome, 0) == (None, None)
    assert os.listdir(tmp_path) == (["beats.json"] if old else []) and (old is None or old.read_bytes() == OLD)


def test_a_candidate_name_that_became_a_symlink_loses_the_link_only_and_a_directory_stays(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"precious")
    link = tmp_path / ".write-beats-aa.tmp"
    link.symlink_to(elsewhere)
    assert beats_hook(tmp_path, link, REVISION, False, None)("failed", 0) == (None, None)
    assert os.listdir(tmp_path) == ["elsewhere"] and elsewhere.read_bytes() == b"precious"
    folder = tmp_path / ".write-beats-bb.tmp"
    folder.mkdir()
    assert beats_hook(tmp_path, folder, REVISION, False, None)("cancelled", 0) == (None, None)
    assert folder.is_dir()


def test_a_redo_replaces_the_old_beats_with_the_candidate_and_the_candidate_is_gone(tmp_path):
    put_old_beats(tmp_path)
    candidate = put_candidate(tmp_path)
    assert swap_beats(tmp_path, candidate, REVISION, True, None) is None
    assert (tmp_path / "beats.json").read_bytes() == sidecar_bytes() and os.listdir(tmp_path) == ["beats.json"]


def test_a_first_run_creates_beats_json_by_link_and_leaves_the_candidate_as_its_second_name_for_the_caller_to_remove(tmp_path):
    candidate = put_candidate(tmp_path)
    assert swap_beats(tmp_path, candidate, REVISION, False, None) is None
    assert (tmp_path / "beats.json").read_bytes() == sidecar_bytes() and candidate.exists()
    assert os.stat(tmp_path / "beats.json").st_nlink == 2


def test_a_first_run_never_overwrites_a_beats_json_made_by_hand_during_the_run(tmp_path):
    candidate = put_candidate(tmp_path)
    put_old_beats(tmp_path)
    assert swap_beats(tmp_path, candidate, REVISION, False, None) == BEATS_EXIST
    assert (tmp_path / "beats.json").read_bytes() == OLD and candidate.exists()


def test_a_candidate_for_another_script_is_refused_and_the_old_beats_stay(tmp_path):
    put_old_beats(tmp_path)
    candidate = put_candidate(tmp_path, sidecar_bytes("f" * 64))
    assert swap_beats(tmp_path, candidate, REVISION, True, None) == BEATS_UNREADABLE
    assert (tmp_path / "beats.json").read_bytes() == OLD


BAD_CANDIDATES = {
    "not-json": b"{not json",
    "an-array": b"[]",
    "wrong-version": sidecar_bytes(version=2),
    "missing-scenes": b'{"version": 1, "script_sha256": "' + REVISION.encode() + b'"}',
}


@pytest.mark.parametrize("name", BAD_CANDIDATES)
def test_a_candidate_that_fails_the_light_check_is_refused_without_raising_and_the_old_beats_stay(tmp_path, name):
    put_old_beats(tmp_path)
    candidate = put_candidate(tmp_path, BAD_CANDIDATES[name])
    assert swap_beats(tmp_path, candidate, REVISION, True, None) == BEATS_UNREADABLE
    assert (tmp_path / "beats.json").read_bytes() == OLD


def test_a_missing_candidate_and_a_symlink_candidate_are_unreadable_and_nothing_outside_is_read(tmp_path):
    put_old_beats(tmp_path)
    assert swap_beats(tmp_path, tmp_path / ".write-beats-aa.tmp", REVISION, True, None) == BEATS_UNREADABLE
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(sidecar_bytes())
    link = tmp_path / ".write-beats-bb.tmp"
    link.symlink_to(elsewhere)
    assert swap_beats(tmp_path, link, REVISION, True, None) == BEATS_UNREADABLE
    assert (tmp_path / "beats.json").read_bytes() == OLD and elsewhere.read_bytes() == sidecar_bytes()


def test_a_redo_whose_target_cannot_be_replaced_says_the_job_could_not_finish_and_raises_nothing(tmp_path):
    (tmp_path / "beats.json").mkdir()
    (tmp_path / "beats.json" / "inside").write_bytes(b"x")
    candidate = put_candidate(tmp_path)
    assert swap_beats(tmp_path, candidate, REVISION, True, None) == COULD_NOT_FINISH
    assert candidate.exists()


def test_the_wavs_are_deleted_last(project):
    old_generation(project)
    order = []
    ops = FileOps(unlink=lambda path: (order.append(path.name), os.unlink(path))[1])
    delete_exact_files(project, None, ops)
    assert order == [*FIXED, "001.wav", "002.wav"]


def test_a_first_run_whose_candidate_became_a_symlink_after_the_read_links_the_symlink_itself_and_never_its_target(tmp_path, monkeypatch):
    candidate = put_candidate(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(sidecar_bytes())
    module = sys.modules["scenevoice.web.swap_beats"]
    real_check = module.beats_light_check

    def swap_in_a_symlink_after_the_read(value):
        candidate.unlink()
        candidate.symlink_to(elsewhere)
        return real_check(value)

    monkeypatch.setattr(module, "beats_light_check", swap_in_a_symlink_after_the_read)
    swap_beats(tmp_path, candidate, REVISION, False, None)
    assert os.stat(elsewhere).st_nlink == 1  # the target of the symlink gained no second name
