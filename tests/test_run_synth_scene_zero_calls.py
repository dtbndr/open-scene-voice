import pytest
from test_run_synth_scene import OLD, PREFIX, Rec, make_out, make_plan, run, snapshot


@pytest.mark.parametrize("scene", [0, -1, 4])
def test_bad_scene_number_makes_no_calls(tmp_path, scene):
    make_out(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=scene)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0 and rec.calls == []


def test_missing_env_makes_no_calls(tmp_path):
    make_out(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, env={})
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0 and rec.calls == []


def test_missing_out_dir_makes_no_calls(tmp_path):
    rec = Rec()
    code, err = run(tmp_path, rec)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert not (tmp_path / "out").exists()
    assert rec.factory_calls == 0


def test_file_at_out_makes_no_calls(tmp_path):
    (tmp_path / "out").write_bytes(b"x")
    rec = Rec()
    code, err = run(tmp_path, rec)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0


def _dir_target(out):
    (out / "audio" / "002.wav").mkdir()


def _link_target(out):
    real = out / "audio" / "real.bin"
    real.write_bytes(OLD)
    (out / "audio" / "002.wav").symlink_to(real)


def _dangling_target(out):
    (out / "audio" / "002.wav").symlink_to(out / "audio" / "nowhere")


@pytest.mark.parametrize("setup", [_dir_target, _link_target, _dangling_target])
def test_non_regular_target_makes_no_calls(tmp_path, setup):
    out = make_out(tmp_path, names=("001.wav",))
    setup(out)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert "002.wav" in err
    assert rec.factory_calls == 0 and rec.calls == []


def test_invalid_plan_makes_no_calls(tmp_path):
    make_out(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    rec = Rec()
    code, err = run(tmp_path, rec, plan=bad)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0


def test_over_limit_body_in_other_scene_makes_no_calls(tmp_path):
    out = make_out(tmp_path)
    before = snapshot(out)
    plan = make_plan(tmp_path, bodies={3: "x" * 100000})
    rec = Rec()
    code, err = run(tmp_path, rec, scene=1, plan=plan)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0 and rec.calls == []
    assert snapshot(out) == before


@pytest.mark.parametrize(
    "opt",
    [
        {"voice": "Nobody"},
        {"model": "bad-model"},
        {"language": "  "},
        {"instruction": "   "},
    ],
)
def test_option_failures_make_no_calls(tmp_path, opt):
    make_out(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, **opt)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0 and rec.calls == []
