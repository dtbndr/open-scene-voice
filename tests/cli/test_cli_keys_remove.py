import os
import stat

from keys_helper import CANARY, posix_only, seed

from scenevoice.cli.main import main

NAME = "OPENROUTER_API_KEY"


def test_remove_removed(key_path, capsys):
    seed(key_path, f"{NAME}='{CANARY}'\nELEVENLABS_API_KEY='el'\n")
    assert main(["keys", "remove", NAME]) == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: removed {NAME}\n"
    assert key_path.read_text() == "ELEVENLABS_API_KEY='el'\n"


def test_remove_absent(key_path, capsys):
    before = seed(key_path, "ELEVENLABS_API_KEY='el'\n")
    assert main(["keys", "remove", NAME]) == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: {NAME} was not saved\n"
    assert key_path.read_bytes() == before


def test_remove_last_name_leaves_empty_file(key_path, capsys):
    seed(key_path, f"{NAME}='{CANARY}'\n")
    assert main(["keys", "remove", NAME]) == 0
    assert key_path.read_bytes() == b""


def test_remove_on_malformed_file_fails(key_path, capsys):
    before = seed(key_path, f"{CANARY} oops without equals\n")
    assert main(["keys", "remove", NAME]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: FAIL key file {key_path}: line 1 is not NAME=value\n"
    assert key_path.read_bytes() == before


@posix_only
def test_loose_file_gets_one_note_and_is_rewritten_0600(key_path, capsys):
    seed(key_path, f"{NAME}='abc'\n", mode=0o644)
    assert main(["keys", "remove", NAME]) == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == (
        f"scenevoice keys: NOTE key file {key_path} can be read by other users; run chmod 600 {key_path}\n"
        f"scenevoice keys: removed {NAME}\n"
    )
    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600
