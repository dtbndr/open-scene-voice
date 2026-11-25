from collections.abc import Mapping
from pathlib import Path

from scenevoice.progress import Failure
from scenevoice.synth.check_elevenlabs_options import check_elevenlabs_options
from scenevoice.synth.check_instruction import check_instruction
from scenevoice.synth.check_language import check_language
from scenevoice.synth.check_model import check_model
from scenevoice.synth.check_voice import check_voice
from scenevoice.synth.defaults import DEFAULT_LANGUAGE
from scenevoice.synth.final_ok_text import final_ok_text
from scenevoice.synth.make_record_hook import make_record_hook
from scenevoice.synth.make_scene_event import make_scene_event
from scenevoice.synth.make_synth_say import make_synth_say
from scenevoice.synth.models import MODELS
from scenevoice.synth.provider import ProviderError, ProviderFactory
from scenevoice.synth.provider_registry import ELEVENLABS, provider_for_model
from scenevoice.synth.record_settings import RecordSettings
from scenevoice.synth.run_preflight import run_preflight
from scenevoice.synth.serialize_record import serialize_record
from scenevoice.synth.synth_scenes import synth_scenes
from scenevoice.synth.write_record_file import write_record_file


def run_synth(
    plan_path: str | Path | None,
    stdin,
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    out_dir: str | Path,
    voice: str,
    model: str,
    language: str | None,
    instruction: str | None,
    provider_factory: ProviderFactory,
    stderr,
    scene: int | None = None,
    key_file_path: str | Path | None = None,
    progress_mode: str = "text",
) -> int:
    """Run the offline synth core; returns 0 on success, 1 on any failure. Never writes stdout."""
    secrets: list[str | None] = []

    say = make_synth_say(stderr, secrets, progress_mode)
    json_mode = progress_mode == "json"

    def fail(text: str, kind: str) -> int:
        """`kind` is the phase-rule kind for a plain text; a Failure keeps its own."""
        if isinstance(text, Failure):  # read before say() redacts the text into a plain str
            fields = dict(kind=text.kind, scene=text.scene, line=text.line, status=text.status)
        else:
            fields = dict(kind=kind, scene=None, line=None, status=None)
        say("FAIL " + text, **fields)
        return 1

    model_violation = check_model(model)
    if model_violation is not None:
        return fail(model_violation.message, "invalid_input")
    spec = provider_for_model(model)
    if spec is None:  # unreachable after check_model; narrows the type
        return fail(f"model must be one of {', '.join(MODELS)}", "invalid_input")
    violation = check_voice(voice, spec.voices)
    if violation is None and spec is ELEVENLABS:
        violation = check_elevenlabs_options(language, instruction)
        language = None
    elif violation is None:
        language = DEFAULT_LANGUAGE if language is None else language
        violation = check_language(language)
        if violation is None and instruction is not None:
            violation = check_instruction(instruction)
    if violation is not None:
        return fail(violation.message, "invalid_input")
    secret_name = spec.secret_env_name
    secrets.append(process_env.get(secret_name))

    def body_check(scenes):
        return spec.check_body_limit(scenes, model)

    settings = RecordSettings(voice, model, language, instruction)

    def note(text: str) -> None:
        say("NOTE " + text)

    prepared = run_preflight(
        plan_path, stdin, process_env, dotenv_path, out_dir, scene,
        spec=spec, body_check=body_check, settings=settings, note=note,
        key_file_path=key_file_path,
    )  # fmt: skip
    if isinstance(prepared, str):
        return fail(prepared, "invalid_input")  # a Failure (missing key) keeps its own kind
    secrets.append(prepared.env.get(secret_name))
    record_hook = None
    if scene is None:  # full run: empty record first, then one rewrite per scene (D8, D9)
        written = write_record_file(out_dir, serialize_record([]))
        if written is not None:
            return fail(written, "invalid_input")
        record_hook = make_record_hook(out_dir, settings, [])
    else:  # scene mode: the parsed entries stay in memory; the record is never re-read (D12)
        record_hook = make_record_hook(out_dir, settings, prepared.entries)
    try:
        provider = provider_factory(prepared.env, model)
    except ProviderError as error:
        return fail(str(error), "other")
    failure = synth_scenes(
        prepared.scenes, instruction, voice, language, out_dir, provider,
        (lambda text: None) if json_mode else say, prepared.total,
        plan=prepared.plan, record_hook=record_hook,
        scene_event=make_scene_event(say) if json_mode else None,
    )  # fmt: skip
    if failure is not None:
        return fail(failure, "other")  # a Failure keeps its own kind
    say(final_ok_text(prepared.scenes, scene, out_dir))
    return 0
