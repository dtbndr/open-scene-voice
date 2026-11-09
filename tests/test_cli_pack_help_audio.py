import pytest

from scenevoice.cli.main import main


def test_pack_help_says_wavs_are_under_dir_audio(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert exc.value.code == 0
    assert "WAV files in DIR/audio" in out
    assert "directory of WAV files" not in out
    assert "next to the synthesized WAV files" not in out
