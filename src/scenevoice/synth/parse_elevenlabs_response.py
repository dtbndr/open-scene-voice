import base64
import json

from scenevoice.synth.accept_alignment import accept_alignment
from scenevoice.synth.clamp_alignment import clamp_alignment
from scenevoice.synth.pcm_to_wav import pcm_to_wav
from scenevoice.synth.provider import ProviderAudio, ProviderError
from scenevoice.synth.read_wav_frames import read_wav_frames

_P = "ElevenLabs response "
_RATE = 24000


def parse_elevenlabs_response(raw: bytes) -> ProviderAudio:
    """Parse an ElevenLabs with-timestamps response body into ProviderAudio (WAV plus alignment).

    Audio rules are checked before alignment rules. Raises ProviderError with a short fixed
    message that never embeds the response body.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProviderError(_P + "is not UTF-8") from None
    try:
        doc = json.loads(text)
    except ValueError:
        raise ProviderError(_P + "is not valid JSON") from None
    if not isinstance(doc, dict):
        raise ProviderError(_P + "is not a JSON object")
    data = doc.get("audio_base64")
    if not isinstance(data, str):
        raise ProviderError(_P + "audio_base64 is not a string")
    try:
        pcm = base64.b64decode(data, validate=True)
    except ValueError:  # binascii.Error
        raise ProviderError(_P + "audio_base64 is not valid base64") from None
    if not pcm:
        raise ProviderError(_P + "audio is empty")
    if len(pcm) % 2:
        raise ProviderError(_P + "audio has an odd byte length")
    accepted = accept_alignment(doc.get("alignment"))
    if isinstance(accepted, str):
        raise ProviderError(_P + accepted)
    wav = pcm_to_wav(pcm)
    frames = read_wav_frames(wav)
    if isinstance(frames, str):
        raise ProviderError(_P + "audio rejected: " + frames)
    return ProviderAudio("audio/wav", wav, clamp_alignment(accepted, frames / _RATE))
