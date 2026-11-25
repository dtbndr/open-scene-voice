import os
from pathlib import Path

from scenevoice.keys import key_file_path

HOME = Path("/home/someone")


def test_override_wins_over_everything() -> None:
    environ = {"SCENEVOICE_KEYS_FILE": "/etc/k.env", "XDG_CONFIG_HOME": "/xdg"}
    assert key_file_path(environ, os_name="posix", home=HOME) == Path("/etc/k.env")


def test_posix_default_is_under_home_config() -> None:
    expected = HOME / ".config" / "scenevoice" / "keys.env"
    assert key_file_path({}, os_name="posix", home=HOME) == expected


def test_absolute_xdg_config_home_is_honoured() -> None:
    environ = {"XDG_CONFIG_HOME": "/xdg"}
    assert key_file_path(environ, os_name="posix", home=HOME) == (
        Path("/xdg") / "scenevoice" / "keys.env"
    )


def test_windows_uses_appdata() -> None:
    appdata = "C:/Users/x/AppData/Roaming"
    result = key_file_path({"APPDATA": appdata}, os_name="nt", home=HOME)
    assert result == Path(appdata) / "scenevoice" / "keys.env"


def test_suite_guard_points_into_tmp_path_and_not_a_real_file(tmp_path: Path) -> None:
    resolved = key_file_path(os.environ)
    assert resolved.is_relative_to(tmp_path)
    assert not resolved.exists()

