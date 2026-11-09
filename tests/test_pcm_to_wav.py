import io
import wave

from scenevoice.synth import pcm_to_wav, read_wav_frames


def test_wrap_is_a_readable_24k_mono_16bit_wav():
    pcm = b"\x00\x00" * 10
    wav = pcm_to_wav(pcm)
    assert read_wav_frames(wav) == 10
    with wave.open(io.BytesIO(wav), "rb") as reader:
        assert (reader.getframerate(), reader.getnchannels(), reader.getsampwidth()) == (24000, 1, 2)
        assert reader.readframes(reader.getnframes()) == pcm


def test_frames_equal_pcm_bytes_for_nonzero_samples():
    pcm = bytes(range(20))
    with wave.open(io.BytesIO(pcm_to_wav(pcm)), "rb") as reader:
        assert reader.readframes(reader.getnframes()) == pcm
