import pytest

from scenevoice.cli.main import main


def test_scene_help_names_synth_record(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["synth", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    text = " ".join(captured.out.split())
    assert "checked against DIR/synth_record.json" in text
    assert "outputs do not record them" not in text
    for phrase in (
        "one provider call",
        "replaces DIR/audio/NNN.wav",
        "must already exist",
        "pass the original --voice",
        "again",
        "--instruction",
    ):
        assert phrase in text
