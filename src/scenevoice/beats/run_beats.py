from collections.abc import Mapping
from pathlib import Path

from scenevoice.beats.build_beats_prompt import build_beats_prompt
from scenevoice.beats.build_beats_request import build_beats_request
from scenevoice.beats.chat_error_kind import chat_error_kind
from scenevoice.beats.check_out_path import check_out_path
from scenevoice.beats.clean_beats_reply import clean_beats_reply
from scenevoice.beats.judge_beats_reply import judge_beats_reply
from scenevoice.beats.make_beats_say import make_beats_say
from scenevoice.beats.read_beats_script import read_beats_script
from scenevoice.beats.report_beats import LENGTH_PROBLEM, report_beats
from scenevoice.beats.segment_scenes import segment_scenes
from scenevoice.beats.write_out_file import write_out_file
from scenevoice.keys import missing_key_message
from scenevoice.openrouter.chat_constants import CHAT_ENV_NAMES
from scenevoice.openrouter.chat_error import ChatError
from scenevoice.openrouter.chat_types import ChatFactory
from scenevoice.openrouter.describe_chat_error import describe_chat_error
from scenevoice.openrouter.parse_chat_response import parse_chat_response
from scenevoice.openrouter.redact_chat_error import redact_chat_error
from scenevoice.synth import redact_secret, resolve_env
from scenevoice.validation import Violation

_KEY = CHAT_ENV_NAMES[0]
_COMMAND = "beats"


def _invalid_note(problems: list[str], truncated: bool) -> str:
    found = ([LENGTH_PROBLEM] if truncated else []) + problems
    if not found:
        return ""
    return "; it is not a valid complete sidecar: " + "; ".join(found)


def run_beats(
    script_path: str | Path,
    out: str | Path,
    model: str,
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    chat_factory: ChatFactory,
    stderr,
    stdout,
    key_file_path: str | Path | None = None,
    progress_mode: str = "text",
) -> int:
    """Split a script's scenes into visual beats with one chat call; returns 0 or 1.

    stdout stays empty unless the file cannot be written after the paid reply came back: then the
    (redacted) text is printed there so it is not lost.
    """
    secrets: list[str | None] = [process_env.get(_KEY)]
    say = make_beats_say(stderr, secrets, progress_mode)

    def fail(text: str, kind: str, status: int | None = None) -> int:
        say("FAIL " + text, kind=kind, status=status)
        return 1

    read = read_beats_script(script_path)
    if isinstance(read, str):
        return fail("SCRIPT: " + read, "invalid_input")
    script_bytes, scenes = read
    problem = check_out_path(out, command=_COMMAND)
    if problem is not None:
        return fail(problem, "invalid_input")
    env = resolve_env(
        process_env,
        dotenv_path,
        CHAT_ENV_NAMES,
        key_file=key_file_path,
        warn=lambda text: say("NOTE " + text),
    )
    if isinstance(env, Violation):
        return fail(env.message, "invalid_input")
    if isinstance(env, list):
        return fail(missing_key_message(env, key_file_path), "missing_key")
    secrets.append(env[_KEY])
    segments = segment_scenes(scenes)
    request = build_beats_request(model, build_beats_prompt(scenes, segments))
    chat = chat_factory(env[_KEY])
    try:
        reply, truncated = parse_chat_response(chat(request))
    except ChatError as error:
        return fail(
            describe_chat_error(
                redact_chat_error(error, secrets),
                reply_thing="beats",
                too_long_hint="try a shorter script",
                blocked_hint="try another model",
            ),
            chat_error_kind(error),
            error.status,
        )
    cleaned, labels = clean_beats_reply(reply)
    text, problems, beat_count = judge_beats_reply(
        cleaned, truncated, script_bytes, scenes, segments
    )
    problem = write_out_file(out, text, command=_COMMAND)
    if problem is not None:
        saved = text
        for secret in secrets:
            saved = redact_secret(saved, secret)
        stdout.write(saved)
        return fail(
            problem + "; the reply was received and may have been charged, "
            "so it is printed on stdout instead" + _invalid_note(problems, truncated),
            "other",
        )
    return report_beats(say, out, labels, problems, truncated, len(scenes), beat_count)
