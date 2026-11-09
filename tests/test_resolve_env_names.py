from scenevoice.synth import ENV_NAMES, resolve_env

K = "OPENROUTER_API_KEY"
NAMES = (K,)


def _env(tmp_path, text):
    path = tmp_path / ".env"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def test_resolves_from_process(tmp_path):
    assert resolve_env({K: "k"}, _env(tmp_path, None), names=NAMES) == {K: "k"}


def test_resolves_from_dotenv(tmp_path):
    assert resolve_env({}, _env(tmp_path, f"{K}=fromfile\n"), names=NAMES) == {K: "fromfile"}


def test_process_wins(tmp_path):
    assert resolve_env({K: "proc"}, _env(tmp_path, f"{K}=file\n"), names=NAMES) == {K: "proc"}


def test_blank_and_whitespace_are_missing(tmp_path):
    assert resolve_env({K: "   "}, _env(tmp_path, f"{K}=\n"), names=NAMES) == [K]
    assert resolve_env({K: ""}, _env(tmp_path, None), names=NAMES) == [K]


def test_blank_process_falls_back_to_dotenv(tmp_path):
    assert resolve_env({K: " "}, _env(tmp_path, f"{K}=file\n"), names=NAMES) == {K: "file"}


def test_only_requested_names_are_reported(tmp_path):
    result = resolve_env({}, _env(tmp_path, None), names=NAMES)
    assert result == [K]


def test_default_still_uses_synth_names(tmp_path):
    assert resolve_env({}, _env(tmp_path, None)) == list(ENV_NAMES)
