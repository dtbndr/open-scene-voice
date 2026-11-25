import os
from pathlib import Path

import pytest

from scenevoice.web import scrub_text


class Dirs:
    """A symlinked tree: `link` resolves to `real`, like /var -> /private/var on macOS."""

    def __init__(self, tmp_path: Path) -> None:
        self.real = tmp_path / "real"
        self.real.mkdir()
        self.link = tmp_path / "link"
        os.symlink(self.real, self.link)
        (self.real / "ws").mkdir()
        (self.real / "launch").mkdir()
        (self.real / "ws" / "my-video").mkdir()
        self.workspace = self.link / "ws"
        self.launch = self.link / "launch"
        self.project = self.workspace / "my-video"
        self.key_file = self.launch / "keys.env"

    def scrub(self, text: str, **overrides: object) -> str:
        arguments: dict[str, object] = {
            "project_dir": self.project,
            "project_id": "my-video",
            "launch_dir": self.launch,
            "workspace": self.workspace,
            "key_file": self.key_file,
        }
        return scrub_text(text, **{**arguments, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def dirs(tmp_path: Path) -> Dirs:
    return Dirs(tmp_path)


def forms(path: Path) -> list[str]:
    return [str(path), str(path.resolve())]


def test_the_symlinked_case_really_has_two_spellings(dirs: Dirs) -> None:
    assert str(dirs.project) != str(dirs.project.resolve())


@pytest.mark.parametrize("spelling", [0, 1])
def test_the_project_folder_becomes_the_project_id_in_both_spellings(dirs: Dirs, spelling: int) -> None:
    folder = forms(dirs.project)[spelling]
    assert dirs.scrub(f"cannot read {folder}/script.txt") == "cannot read my-video/script.txt"


@pytest.mark.parametrize("spelling", [0, 1])
def test_the_launch_directory_and_the_workspace_are_removed_with_their_trailing_slash(dirs: Dirs, spelling: int) -> None:
    launch = forms(dirs.launch)[spelling]
    workspace = forms(dirs.workspace)[spelling]
    assert dirs.scrub(f"bad {launch}/check.txt") == "bad check.txt"
    assert dirs.scrub(f"bad {workspace}/other/x.txt") == "bad other/x.txt"
    assert dirs.scrub(f"in {launch}") == "in "
    assert dirs.scrub(f"in {workspace}/") == "in "


@pytest.mark.parametrize("spelling", [0, 1])
def test_the_key_file_becomes_the_key_file_and_wins_over_the_directory_holding_it(dirs: Dirs, spelling: int) -> None:
    key_file = forms(dirs.key_file)[spelling]
    assert dirs.scrub(f"cannot write {key_file}") == "cannot write the key file"


def test_longest_first_sends_the_project_folder_to_its_id_even_when_the_workspace_is_a_prefix(dirs: Dirs) -> None:
    result = dirs.scrub(f"{dirs.project}/a and {dirs.workspace}/b", project_id="the-id")
    assert result == "the-id/a and b"


def test_a_message_with_none_of_the_paths_is_unchanged(dirs: Dirs) -> None:
    text = "Scene 3 has no text. See /usr/local/other/path and my-video."
    assert dirs.scrub(text) == text


def test_missing_project_and_key_file_are_skipped(dirs: Dirs) -> None:
    text = f"{dirs.workspace}/x and {dirs.key_file}"
    assert dirs.scrub(text, project_dir=None, project_id=None, key_file=None) == "x and keys.env"


def test_paths_with_pattern_characters_are_matched_literally(tmp_path: Path) -> None:
    odd = tmp_path / "w[1]+(x)*.?"
    odd.mkdir()
    launch = tmp_path / "launch"
    launch.mkdir()
    result = scrub_text(
        f"in {odd}/file and w1xxx/file and {odd.resolve()}/b",
        project_dir=None,
        project_id=None,
        launch_dir=launch,
        workspace=odd,
        key_file=None,
    )
    assert result == "in file and w1xxx/file and b"
