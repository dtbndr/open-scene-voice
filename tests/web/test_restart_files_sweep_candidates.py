import os
import sys
from pathlib import Path

from restart_helper import snapshot

from scenevoice.web import PlannedScene, build_synth_argv, sweep_candidates
from scenevoice.web.rest_runs import rest_runs

LEFTOVER = ".write-beats-0123456789abcdef.tmp"
ASIDE = ".write-restart-0123abcd-synth_record.json.tmp"
RESTORE = ".write-restore-0123abcd-synth_record.json.tmp"


def test_a_leftover_candidate_in_the_project_folder_is_removed_and_nothing_else(tmp_path):
    (tmp_path / LEFTOVER).write_bytes(b"half")
    (tmp_path / "beats.json").write_bytes(b"keep")
    (tmp_path / "script.md").write_bytes(b"keep")
    sweep_candidates(tmp_path)
    assert sorted(os.listdir(tmp_path)) == ["beats.json", "script.md"]


def test_the_restart_backups_and_restore_temps_are_never_swept_in_the_folder_or_in_audio(tmp_path):
    (tmp_path / "audio").mkdir()
    kept = [ASIDE, RESTORE, ".write-restart-0123abcd-line_timings.json.tmp", f"audio/{ASIDE.replace('synth_record.json', '001.wav')}", f"audio/{RESTORE.replace('synth_record.json', '001.wav')}"]
    for name in kept:
        (tmp_path / name).write_bytes(f"backup {name}".encode())
    (tmp_path / LEFTOVER).write_bytes(b"half")
    before = snapshot(tmp_path)
    sweep_candidates(tmp_path)
    assert snapshot(tmp_path) == {name: data for name, data in before.items() if name != LEFTOVER}


def test_other_write_temps_and_a_candidate_inside_audio_are_untouched(tmp_path):
    (tmp_path / "audio").mkdir()
    names = [".write-script.md.tmp", ".write-beats-xyz.tmp", ".write-beats-.tmp", ".write-beats-aa.tmp.bak", "write-beats-aa.tmp", f"audio/{LEFTOVER}", "audio/.write-001.wav.tmp"]
    for name in names:
        (tmp_path / name).write_bytes(b"keep")
    before = snapshot(tmp_path)
    sweep_candidates(tmp_path)
    assert snapshot(tmp_path) == before


def test_a_symlink_or_directory_with_a_candidate_name_is_never_followed_or_removed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious").write_bytes(b"precious")
    project = tmp_path / "project"
    project.mkdir()
    (project / ".write-beats-aa.tmp").symlink_to(outside / "precious")
    (project / ".write-beats-bb.tmp").symlink_to(tmp_path / "nowhere")
    (project / ".write-beats-cc.tmp").symlink_to(outside)
    (project / ".write-beats-dd.tmp").mkdir()
    (project / ".write-beats-dd.tmp" / "inside").write_bytes(b"inside")
    sweep_candidates(project)
    assert sorted(os.listdir(project)) == [".write-beats-aa.tmp", ".write-beats-bb.tmp", ".write-beats-cc.tmp", ".write-beats-dd.tmp"]
    assert (outside / "precious").read_bytes() == b"precious" and (project / ".write-beats-dd.tmp" / "inside").exists()


def test_a_candidate_that_cannot_be_removed_does_not_stop_the_sweep_or_raise(tmp_path, monkeypatch):
    for name in (".write-beats-aa.tmp", ".write-beats-bb.tmp"):
        (tmp_path / name).write_bytes(b"half")
    real = os.unlink
    attempts = []

    def failing(path, *args, **kwargs):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("no")
        real(path, *args, **kwargs)

    monkeypatch.setattr(sys.modules["scenevoice.web.sweep_candidates"].os, "unlink", failing)
    sweep_candidates(tmp_path)
    assert len(attempts) == 2 and len(os.listdir(tmp_path)) == 1


def test_a_candidate_name_hard_linked_to_beats_json_loses_only_that_name_and_beats_json_keeps_its_bytes(tmp_path):
    (tmp_path / "beats.json").write_bytes(b"the beats")
    os.link(tmp_path / "beats.json", tmp_path / ".write-beats-0123456789abcdef.tmp")
    sweep_candidates(tmp_path)
    assert sorted(os.listdir(tmp_path)) == ["beats.json"]
    assert (tmp_path / "beats.json").read_bytes() == b"the beats" and os.stat(tmp_path / "beats.json").st_nlink == 1


SCENES = (PlannedScene(2, "Two", "b"), PlannedScene(5, "Five", "e"))
SETTINGS = {"voice": "Leda", "model": "gemini-3.8-flash-tts", "language": "en-GB", "instruction": None}


def test_one_argument_list_per_unvoiced_scene_in_order_over_one_plan_file_with_the_records_settings():
    runs = rest_runs(Path("/x/plan-1.json"), Path("/w/p"), SCENES, SETTINGS)
    assert runs == [
        build_synth_argv(Path("/x/plan-1.json"), Path("/w/p"), voice="Leda", model="gemini-3.8-flash-tts", language="en-GB", instruction=None, scene=n)
        for n in (2, 5)
    ]
    assert [run[-3] for run in runs] == ["--scene=2", "--scene=5"] and {run[1] for run in runs} == {"/x/plan-1.json"}


def test_no_scene_left_means_no_run():
    assert rest_runs(Path("/x/plan-1.json"), Path("/w/p"), (), SETTINGS) == []
