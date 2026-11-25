"""Usage-error driver for `synth` shared by the Gemini and ElevenLabs usage tests."""

import pytest

from scenevoice.cli.main import main


def run_usage(probes, argv, capsys):
    """Run `synth argv`, assert a pure argparse exit 2 that touched no I/O, return the capture."""
    with pytest.raises(SystemExit) as exc:
        main(["synth", *argv], provider_factory=probes.factory)
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert probes.stdin.touched == []
    assert probes.factory_calls == []
    assert not [f for f in probes.opened if f.endswith((".env", "plan.json"))]
    assert not probes.out.exists()
    return captured


def reaches_core(probes, argv, capsys):
    """Run `synth argv` where argparse accepts everything: the core runs and fails (exit 1)."""
    try:
        code = main(["synth", *argv], provider_factory=probes.factory)
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    assert code == 1  # the stdin/factory fakes fail inside the core; never argparse's 2
    assert captured.out == ""
    assert "error:" not in captured.err
    return captured
