"""Recording stand-in for `python -m scenevoice`; the `stub_cli` fixture copies it to a tmp dir.

Reads `spec.json` beside itself, records argv, stdin bytes, cwd and the named environment
variables to `recording.json`, then replays canned output. Spec keys (all optional):
`stdout`, `stdout_hex` (raw bytes, wins over `stdout`), `stderr_lines`, `stderr_hex` (raw bytes,
wins over `stderr_lines`), `exit_code`,
`record_env` (names to record), `sleep` (seconds to wait after recording), `wait_for_file` (poll until
that path exists, after recording), `by_verb` (maps argv[1] after the group, for example `set`, to a dict
overriding the spec for that call), `record_files` (argv indices, -1 is the last item: the file named there is
read at call time and its path, bytes and mode go to `recording.json` under `files`), and a `{path}` placeholder in
`stderr_lines` replaced (plain `str.replace`, the lines are JSON text) with the last argv item.
Job-runner keys (all optional, all happen before the `start` event so `start` means ready): `sigint` (`"ignore"` or `"exit"`:
install a SIGINT handler; `"exit"` exits with `sigint_exit_code`, default 0), `sigint_marker` (a path appended to by the
handler), `spawn_grandchild` (a path that receives the pid of a same-group, SIGINT-ignoring sleeper that inherits the pipes),
`write_files` (path to text, written before `start`), `write_out_hex` (raw bytes written before `start` to the path that follows `--out` in argv, exclusively created like the CLI does), `stderr_delay` (seconds slept after each stderr line, flushed one by one),
`flood_stdout` and `flood_stderr` (byte counts written concurrently by two threads). Every call also appends to `calls.jsonl` and writes `start` and `end`
lines to `events.jsonl` (monotonic nanoseconds), so tests can order overlapping calls.
"""

import base64
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

here = Path(__file__).resolve()
spec = json.loads(here.with_name("spec.json").read_text(encoding="utf-8"))
if len(sys.argv) > 2:
    spec = {**spec, **spec.get("by_verb", {}).get(sys.argv[2], {})}
stdin_bytes = sys.stdin.buffer.read()


def append(name, line):
    descriptor = os.open(str(here.with_name(name)), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, (json.dumps(line) + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)


def read_file(index):
    path = sys.argv[1:][index]
    data = Path(path).read_bytes()
    return {
        "index": index,
        "path": path,
        "bytes_b64": base64.b64encode(data).decode("ascii"),
        "mode": os.stat(path).st_mode & 0o777,
    }


recording = {
    "files": [read_file(index) for index in spec.get("record_files", [])],
    "argv": sys.argv[1:],
    "stdin_b64": base64.b64encode(stdin_bytes).decode("ascii"),
    "pid": os.getpid(),
    "pgid": os.getpgrp(),
    "cwd": os.getcwd(),
    "env": {name: os.environ.get(name) for name in spec.get("record_env", [])},
    "env_values": sorted(os.environ.values()),
}
here.with_name("recording.json").write_text(json.dumps(recording), encoding="utf-8")
append("calls.jsonl", recording)
if "sigint" in spec:

    def on_sigint(signum, frame):
        if "sigint_marker" in spec:
            with open(spec["sigint_marker"], "a", encoding="utf-8") as marker:
                marker.write("sigint\n")
        if spec["sigint"] == "exit":
            os._exit(spec.get("sigint_exit_code", 0))

    signal.signal(signal.SIGINT, on_sigint)
if "spawn_grandchild" in spec:
    sleeper = (
        "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); time.sleep(120)"
    )
    grandchild = subprocess.Popen([sys.executable, "-c", sleeper])
    Path(spec["spawn_grandchild"]).write_text(str(grandchild.pid), encoding="utf-8")
for file_path, text in spec.get("write_files", {}).items():
    Path(file_path).write_text(text, encoding="utf-8")
if "write_out_hex" in spec and "--out" in sys.argv:
    out_path = sys.argv[sys.argv.index("--out") + 1]
    with open(out_path, "xb") as out_file:
        out_file.write(bytes.fromhex(spec["write_out_hex"]))
append("events.jsonl", {"event": "start", "argv": sys.argv[1:], "t": time.monotonic_ns()})
time.sleep(spec.get("sleep", 0))
release = spec.get("wait_for_file")
deadline = time.monotonic() + 20
while release and not Path(release).exists() and time.monotonic() < deadline:
    time.sleep(0.01)
append("events.jsonl", {"event": "end", "argv": sys.argv[1:], "t": time.monotonic_ns()})
if "stdout_hex" in spec:
    sys.stdout.buffer.write(bytes.fromhex(spec["stdout_hex"]))
else:
    sys.stdout.buffer.write(spec.get("stdout", "").encode("utf-8"))
sys.stdout.buffer.flush()
if "stderr_hex" in spec:
    sys.stderr.buffer.write(bytes.fromhex(spec["stderr_hex"]))
else:
    for line in spec.get("stderr_lines", []):
        sys.stderr.buffer.write((line.replace("{path}", sys.argv[-1]) + "\n").encode("utf-8"))
        if "stderr_delay" in spec:
            sys.stderr.buffer.flush()
            time.sleep(spec["stderr_delay"])
sys.stderr.buffer.flush()


def flood(stream, total, line):
    for _ in range(total // len(line)):
        stream.write(line)
    stream.flush()


flooders = [
    threading.Thread(target=flood, args=(sys.stdout.buffer, spec["flood_stdout"], b"o" * 1023 + b"\n"))
    for _ in [0]
    if "flood_stdout" in spec
] + [
    threading.Thread(target=flood, args=(sys.stderr.buffer, spec["flood_stderr"], b"e" * 1023 + b"\n"))
    for _ in [0]
    if "flood_stderr" in spec
]
for flooder in flooders:
    flooder.start()
for flooder in flooders:
    flooder.join()
sys.exit(spec.get("exit_code", 0))
