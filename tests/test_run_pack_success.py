import inspect
import io

from pack_run_helper import FakeStdin, plan_bytes, put_wav, scene, write_plan

from scenevoice.pack import run_pack

EXPECTED = (
    b"scene,label,file,duration_s\n"
    b"1,One,audio/001.wav,1.000\n"
    b'2,"Two, too",audio/002.wav,2.000\n'
)


def _setup(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 24000)
    put_wav(out, 2, 48000)
    return out


_SCENES = [scene(1, "One"), scene(2, "Two, too")]


def test_two_scene_run_from_plan_path(tmp_path):
    out = _setup(tmp_path)
    err = io.StringIO()
    code = run_pack(write_plan(tmp_path, _SCENES), FakeStdin(b""), out, err)
    assert code == 0
    assert (out / "scene_manifest.csv").read_bytes() == EXPECTED
    line = err.getvalue()
    assert line.startswith("scenevoice pack: OK 2 scenes written to ")
    assert line.endswith("scene_manifest.csv\n")
    assert str(out / "scene_manifest.csv") in line


def test_two_scene_run_from_stdin_buffer(tmp_path):
    out = _setup(tmp_path)
    err = io.StringIO()
    stdin = FakeStdin(plan_bytes(_SCENES), tty=False)
    assert run_pack(None, stdin, out, err) == 0
    assert (out / "scene_manifest.csv").read_bytes() == EXPECTED
    assert err.getvalue().startswith("scenevoice pack: OK 2 scenes written to ")


def test_runner_has_plan_stdin_directory_stderr_then_optional_editor():
    parameters = inspect.signature(run_pack).parameters
    assert list(parameters) == ["plan_path", "stdin", "directory", "stderr", "editor"]
    assert parameters["editor"].default is None


def test_run_needs_no_dotenv_and_writes_nothing_but_manifest(tmp_path):
    out = _setup(tmp_path)
    plan = write_plan(tmp_path, _SCENES)
    assert not (tmp_path / ".env").exists() and not (out / ".env").exists()
    assert run_pack(plan, FakeStdin(b""), out, io.StringIO()) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "audio",
        "scene_manifest.csv",
    ]
    assert sorted(p.name for p in (out / "audio").iterdir()) == ["001.wav", "002.wav"]


def test_stdout_stays_empty(tmp_path, capsys):
    out = _setup(tmp_path)
    run_pack(write_plan(tmp_path, _SCENES), FakeStdin(b""), out, io.StringIO())
    assert capsys.readouterr().out == ""
