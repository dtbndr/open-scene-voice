import pytest

from scenevoice.cli.main import main


def test_synth_help_says_out_holds_wavs_under_audio(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["synth", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert exc.value.code == 0
    assert "the WAV files are written to DIR/audio" in out
    assert "output directory for the WAV files" not in out
