import os

import pytest

from scenevoice.synth import run_preflight

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="permissions not enforced for root"
)
def test_preexisting_unwritable_audio_dir_fails_at_the_probe(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b'{"scenes": [{"ordinal": 1, "title": "t", "body": "b"}]}')
    out = tmp_path / "out"
    audio = out / "audio"
    audio.mkdir(parents=True)
    audio.chmod(0o500)
    try:
        result = run_preflight(plan, None, ENV, tmp_path / "absent.env", out)
        listing = os.listdir(audio)
    finally:
        audio.chmod(0o700)
    assert isinstance(result, str)
    assert not result.startswith("scenevoice synth")
    assert "dummy-key-value" not in result
    assert listing == []
