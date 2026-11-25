import hashlib

from scenevoice.align.match_scene import match_scene
from scenevoice.align.parse_transcription import parse_transcription
from scenevoice.align.scene_timings import SceneTimings
from scenevoice.align.split_sentences import split_sentences
from scenevoice.align.transcriber import Transcriber
from scenevoice.align.transcription_error import TranscriptionError
from scenevoice.pack import LineTiming
from scenevoice.progress import Failure, failure_kind
from scenevoice.synth import PlanScene, ProviderError, SceneWav


def _provider_failure(error: ProviderError) -> Failure:
    if isinstance(error, TranscriptionError) and error.status is not None:
        suffix = f": {error.text}" if error.text else ""
        message = f"provider error (HTTP {error.status}){suffix}"
    else:
        text = error.text if isinstance(error, TranscriptionError) else str(error)
        message = f"provider request failed: {text}" if text else "provider request failed"
    if isinstance(error, TranscriptionError):
        kind = failure_kind("openrouter", error.status, transport=error.transport)
        return Failure(message, kind=kind, status=error.status)
    return Failure(message, kind="other")


def align_scene(
    scene: PlanScene, wav: SceneWav, transcriber: Transcriber
) -> SceneTimings | Failure:
    """One provider call on the held bytes, then match; a classified one-line reason (no scene prefix) on failure."""
    try:
        body = transcriber(wav.data)
    except ProviderError as error:
        return _provider_failure(error)
    except Exception as error:
        return Failure(f"provider request failed: {type(error).__name__}", kind="other")
    if not isinstance(body, bytes | bytearray):
        return Failure("malformed response: response is not bytes", kind="other")
    heard = parse_transcription(body)
    if isinstance(heard, str):
        return Failure(f"malformed response: {heard}", kind="other")
    sentences = split_sentences(scene.body)
    starts = match_scene(sentences, heard)
    lines = [LineTiming(text, start) for text, start in zip(sentences, starts, strict=True)]
    return SceneTimings(scene.ordinal, hashlib.sha256(wav.data).hexdigest(), lines)
