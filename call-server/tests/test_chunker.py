import io
import wave
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chunker import ParticipantAudioChunker, pcm_to_wav, is_pure_silence

# Helper to generate non-silent 1024-byte PCM16 frame
def make_audio_frame(amplitude: int = 2000) -> bytes:
    import struct
    # 512 samples of sine/alternating wave
    samples = [amplitude if i % 2 == 0 else -amplitude for i in range(512)]
    return struct.pack("<512h", *samples)

SILENT_FRAME = b"\x00" * 1024


def test_valid_wav_container():
    frame = make_audio_frame() * 20  # ~640 ms
    wav_bytes = pcm_to_wav(frame)

    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == len(frame) // 2


def test_pre_roll_included():
    chunker = ParticipantAudioChunker("p-1")
    frame = make_audio_frame(amplitude=1500)

    # Feed 15 frames before speech_start (pre-roll)
    for _ in range(15):
        chunker.add_frame(frame)

    assert len(chunker.pre_roll) == 15
    assert len(chunker.buffer) == 0

    chunker.on_vad_speech_start()
    # Buffer should now contain the 15 pre-roll frames (15 * 1024 = 15360 bytes)
    assert len(chunker.buffer) == 15360


def test_wrong_size_frames_ignored():
    chunker = ParticipantAudioChunker("p-1")
    chunker.on_vad_speech_start()

    # Wrong frame sizes
    assert chunker.add_frame(b"short") is None
    assert chunker.add_frame(b"\x00" * 2048) is None
    assert len(chunker.buffer) == 0


def test_continuous_speech_8_6_seconds_gives_2_chunks():
    chunker = ParticipantAudioChunker("p-1")
    frame = make_audio_frame(amplitude=2000)
    chunker.on_vad_speech_start()

    chunks = []
    # 8.6 seconds = 8.6 / 0.032 = ~268 frames
    # At 4.0s (128000 bytes = 125 frames): chunk 1 cut
    # At 8.0s (250 frames): chunk 2 cut
    # Remaining 18 frames remain in buffer
    for _ in range(268):
        c = chunker.add_frame(frame)
        if c:
            chunks.append(c)

    assert len(chunks) == 2
    assert chunks[0][0] == "p-1-0"
    assert chunks[1][0] == "p-1-1"

    for cid, wav_bytes in chunks:
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            dur_s = wf.getnframes() / wf.getframerate()
            assert dur_s <= 4.05


def test_short_chunk_dropped():
    chunker = ParticipantAudioChunker("p-1")
    frame = make_audio_frame()
    chunker.on_vad_speech_start()

    # Feed only 5 frames = 160 ms (< 400 ms)
    for _ in range(5):
        chunker.add_frame(frame)

    result = chunker.on_vad_speech_end()
    assert result is None
    assert len(chunker.buffer) == 0


def test_pure_silence_dropped():
    chunker = ParticipantAudioChunker("p-1")
    chunker.on_vad_speech_start()

    # Feed 20 frames of pure silence = 640 ms (> 400 ms)
    for _ in range(20):
        chunker.add_frame(SILENT_FRAME)

    result = chunker.on_vad_speech_end()
    assert result is None


def test_sequential_chunk_ids_increase():
    chunker = ParticipantAudioChunker("p-tester")
    frame = make_audio_frame()
    chunker.on_vad_speech_start()

    # 1st chunk
    for _ in range(20):
        chunker.add_frame(frame)
    c1 = chunker.on_vad_speech_end()
    assert c1 is not None
    assert c1[0] == "p-tester-0"

    # 2nd chunk
    chunker.on_vad_speech_start()
    for _ in range(20):
        chunker.add_frame(frame)
    c2 = chunker.on_vad_speech_end()
    assert c2 is not None
    assert c2[0] == "p-tester-1"
