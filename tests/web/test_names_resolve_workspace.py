import os
from pathlib import Path

import pytest

from scenevoice.web import (
    WorkspaceError,
    WorkspaceKeyFileError,
    real_root,
    resolve_workspace,
)


def test_default_is_documents_scenevoice_under_the_passed_home(tmp_path):
    assert resolve_workspace({}, home=tmp_path) == tmp_path / "Documents" / "SceneVoice"


def test_absolute_environment_value_overrides_the_default(tmp_path):
    env = {"SCENEVOICE_WORKSPACE": str(tmp_path / "ws")}
    assert resolve_workspace(env, home=Path("/nonexistent-home")) == tmp_path / "ws"


@pytest.mark.parametrize("blank", ["", " ", "\t \n"])
def test_blank_value_counts_as_unset(blank, tmp_path):
    assert resolve_workspace({"SCENEVOICE_WORKSPACE": blank}, home=tmp_path) == tmp_path / "Documents" / "SceneVoice"


@pytest.mark.parametrize("bad", ["relative/ws", "~/ws", "~", "./ws"])
def test_relative_or_tilde_value_is_refused_naming_the_variable(bad, tmp_path):
    with pytest.raises(WorkspaceError) as caught:
        resolve_workspace({"SCENEVOICE_WORKSPACE": bad}, home=tmp_path)
    assert "SCENEVOICE_WORKSPACE" in str(caught.value)
    assert "absolute path" in str(caught.value)


def test_injected_override_wins_and_relative_one_is_refused(tmp_path):
    assert resolve_workspace({"SCENEVOICE_WORKSPACE": "/ignored"}, override=tmp_path / "x", home=tmp_path) == tmp_path / "x"
    with pytest.raises(WorkspaceError):
        resolve_workspace({}, override=Path("rel"), home=tmp_path)


def test_no_filesystem_call_is_made(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(os.path, "realpath", lambda p, **k: calls.append("realpath") or p)
    monkeypatch.setattr(os, "lstat", lambda p, **k: calls.append("lstat") or None)
    result = resolve_workspace({"SCENEVOICE_WORKSPACE": str(tmp_path / "new")}, home=tmp_path)
    assert result == tmp_path / "new"
    assert calls == []
    assert not (tmp_path / "new").exists()
    # positive control: the patches are live
    os.path.realpath(tmp_path)
    assert calls == ["realpath"]


def test_real_root_resolves_a_symlinked_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    assert real_root(link) == target.resolve()


def test_real_root_allows_a_missing_root_without_creating_it(tmp_path):
    missing = tmp_path / "no" / "such"
    assert real_root(missing) == tmp_path.resolve() / "no" / "such"
    assert not (tmp_path / "no").exists()


def test_real_root_refuses_a_workspace_holding_the_key_file(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(WorkspaceKeyFileError) as caught:
        real_root(ws, key_file=ws / "keys.env")
    assert str(caught.value) == "The workspace folder holds your key file. Choose another folder."
    assert isinstance(caught.value, WorkspaceError)


def test_real_root_catches_a_symlink_onto_the_key_folder(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    ws = tmp_path / "ws"
    ws.symlink_to(keys)
    with pytest.raises(WorkspaceKeyFileError):
        real_root(ws, key_file=keys / "keys.env")


def test_real_root_accepts_an_unrelated_key_file(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert real_root(ws, key_file=tmp_path / "keys.env") == ws.resolve()
