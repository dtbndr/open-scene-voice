"""D1: one WAV snapshot. The hash and the transcriber argument come from the bytes held after check 5."""

import builtins
import hashlib
import io
import json
from pathlib import Path

from align_run_helper import ENV, HELLO, NoTerminal, body, pack_dir
from record_helper import eleven_entry, write_record
from wav_helper import make_wav

from scenevoice.align.run_align import run_align


class ReadCounter:
    """Counts read-mode opens of *.wav (count) and synth_record.json (record_count) through open."""

    def __init__(self, monkeypatch):
        self.count = 0
        self.record_count = 0
        counter = self

        def wrap(real, mode_index):
            def counted(*args, **kwargs):
                target = args[0]
                mode = kwargs.get("mode", args[mode_index] if len(args) > mode_index else "r")
                if str(target).endswith(".wav") and "r" in mode:
                    counter.count += 1
                if str(target).endswith("synth_record.json") and "r" in mode:
                    counter.record_count += 1
                return real(*args, **kwargs)

            return counted

        monkeypatch.setattr(builtins, "open", wrap(builtins.open, 1))
        monkeypatch.setattr(io, "open", wrap(io.open, 1))


def test_read_counter_positive_control(tmp_path, monkeypatch):
    wav = tmp_path / "x.wav"
    wav.write_bytes(make_wav(3))
    counter = ReadCounter(monkeypatch)
    wav.write_bytes(make_wav(4))
    assert counter.count == 0
    wav.read_bytes()
    assert counter.count == 1
    with open(wav, "rb") as handle:
        handle.read()
    assert counter.count == 2
    Path(wav).open("rb").close()
    assert counter.count == 3
    record = tmp_path / "synth_record.json"
    record.write_text("{}")
    assert counter.record_count == 0
    record.read_text()
    assert counter.record_count == 1
    assert counter.count == 3


def test_snapshot_survives_rewrites_of_the_files_on_disk(tmp_path, monkeypatch):
    plan_path, out, wavs = pack_dir(tmp_path, ["Hello there.", "Hello there."])
    audio = out / "audio"
    counter = ReadCounter(monkeypatch)
    received = []
    marks = {}

    def factory(key):
        marks["after_check_5"] = counter.count
        return transcriber

    def transcriber(wav):
        received.append(wav)
        if len(received) == 1:
            (audio / "001.wav").write_bytes(make_wav(7777))
            (audio / "002.wav").write_bytes(make_wav(8888))
        return body(HELLO)

    err = io.StringIO()
    code = run_align(plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, factory, err)
    reads_after = counter.count
    assert code == 0
    assert received == wavs
    data = json.loads((out / "line_timings.json").read_text())
    assert [scene["sha256"] for scene in data["scenes"]] == [
        hashlib.sha256(w).hexdigest() for w in wavs
    ]
    assert (audio / "001.wav").read_bytes() != wavs[0]
    assert reads_after == marks["after_check_5"]  # no WAV read after check 5


def test_no_wav_read_after_check_5(tmp_path, monkeypatch):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there.", "Hello there.", "Hello there."])
    counter = ReadCounter(monkeypatch)
    marks = {}

    def factory(key):
        marks["before"] = counter.count
        return lambda wav: body(HELLO)

    code = run_align(plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, factory, io.StringIO())
    assert code == 0
    assert marks["before"] == 3
    assert counter.count == 3


def test_all_record_run_reads_the_record_once_and_each_wav_once(tmp_path, monkeypatch):
    texts = ["Hello there.", "Hello there."]
    plan_path, out, wavs = pack_dir(tmp_path, texts)
    write_record(out, *(eleven_entry(n, w, t) for n, (w, t) in enumerate(zip(wavs, texts, strict=True), 1)))
    counter = ReadCounter(monkeypatch)
    code = run_align(
        plan_path, NoTerminal(), {}, tmp_path / "no.env", out, lambda k: None, io.StringIO()
    )
    assert code == 0
    assert counter.record_count == 1
    assert counter.count == 2
