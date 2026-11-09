from test_run_synth_scene import NEW_AUDIO, OLD, PREFIX, Rec, make_out, run


def test_scene_writes_under_audio_and_reports_audio_paths(tmp_path):
    out = make_out(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 0
    assert (out / "audio" / "002.wav").read_bytes() == NEW_AUDIO.wav
    assert err.splitlines() == [
        PREFIX + "NOTE no settings recorded for scene 2 (synth_record.json is missing); settings not checked",
        PREFIX + "scene 2/3 written to audio/002.wav",
        PREFIX + f"OK scene 2 written to {out}/audio/002.wav",
    ]


def test_flat_wav_is_untouched_and_not_checked(tmp_path):
    out = make_out(tmp_path)
    (out / "002.wav").mkdir()  # a flat directory of that name would be refused if looked at
    code, _ = run(tmp_path, Rec(), scene=2)
    assert code == 0
    assert (out / "002.wav").is_dir()


def test_missing_audio_dir_fails_with_no_call_and_creates_nothing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "002.wav").write_bytes(OLD)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 1
    assert err.splitlines()[-1] == PREFIX + "FAIL --out/audio does not exist or is not a directory"
    assert rec.factory_calls == 0 and rec.calls == []
    assert sorted(p.name for p in out.iterdir()) == ["002.wav"]


def test_symlinked_audio_fails_with_no_call(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (out / "audio").symlink_to(tmp_path / "elsewhere")
    rec = Rec()
    code, err = run(tmp_path, rec, scene=1)
    assert code == 1 and "--out/audio does not exist or is not a directory" in err
    assert rec.factory_calls == 0
    assert list((tmp_path / "elsewhere").iterdir()) == []
