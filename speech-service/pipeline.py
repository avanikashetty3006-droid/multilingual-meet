"""The real speech pipeline (ASR -> MT -> TTS), independent of FastAPI and of any ML library.

Engines are plain objects with these methods, so tests can use fakes and the real ones live in engines.py:
    asr.transcribe(samples_16k_float32, language_or_None, prev_text) -> (segments, detected_lang_or_None)
        segments = [{"text": str, "no_speech_prob": float, "avg_logprob": float}, ...]
    mt.translate(text, src_lang, tgt_lang) -> str            (raise on failure)
    tts.synthesize(text, lang) -> bytes (a WAV file)         (raise on failure)
"""
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from audio_io import TARGET_SR, decode_wav, resample, rms
from langs import SUPPORTED

log = logging.getLogger("speech-pipeline")

NO_SPEECH_MAX = 0.6        # Whisper hallucination guard (see ROLE 3 prompt)
AVG_LOGPROB_MIN = -1.0
SILENCE_RMS = 0.009        # about 300 on the int16 scale: quieter than this is silence/noise, skip Whisper


def empty_result(detected: str) -> dict:
    return {"detected_lang": detected, "source_text": "", "translations": {},
            "timings_ms": {"asr": 0, "mt": 0, "tts": 0}}


def ms_since(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


class Pipeline:
    def __init__(self, asr, mt, tts, audio_dir: Path, public_url: str):
        self.asr, self.mt, self.tts = asr, mt, tts
        self.audio_dir = Path(audio_dir)
        self.public_url = public_url.rstrip("/")
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def keep_segments(segments: List[dict]) -> str:
        kept = []
        for s in segments:
            if s.get("no_speech_prob", 0.0) > NO_SPEECH_MAX or s.get("avg_logprob", 0.0) < AVG_LOGPROB_MIN:
                log.info("dropped likely hallucination: %r (no_speech=%.2f logprob=%.2f)",
                         s.get("text"), s.get("no_speech_prob", 0), s.get("avg_logprob", 0))
                continue
            t = (s.get("text") or "").strip()
            if t:
                kept.append(t)
        return " ".join(kept).strip()

    def _save_wav(self, wav_bytes: bytes) -> str:
        name = f"{uuid.uuid4().hex}.wav"
        (self.audio_dir / name).write_bytes(wav_bytes)
        return f"{self.public_url}/audio/{name}"

    # --------------------------------------------------------------------- main
    def run(self, wav_bytes: bytes, src_lang: str, tgt_langs: List[str], want_audio: bool, prev_text: str = "") -> dict:
        guess = src_lang if src_lang in SUPPORTED else "en"
        dec = decode_wav(wav_bytes)
        if dec is None:
            return empty_result(guess)
        samples, sr = dec
        if rms(samples) < SILENCE_RMS:
            return empty_result(guess)
        samples = resample(samples, sr, TARGET_SR)

        # ---- ASR
        t0 = time.perf_counter()
        language = src_lang if src_lang in SUPPORTED else None  # None = let Whisper detect
        segments, detected = self.asr.transcribe(samples, language, prev_text or None)
        asr_ms = ms_since(t0)
        text = self.keep_segments(segments)
        detected = detected or language or "en"
        if not text:
            r = empty_result(detected)
            r["timings_ms"]["asr"] = asr_ms
            return r

        # ---- MT (once per unique target language; one failure never fails the request)
        t0 = time.perf_counter()
        translations: Dict[str, dict] = {}
        for tgt in dict.fromkeys(tgt_langs):  # de-duplicate, keep order
            if tgt == detected:
                translations[tgt] = {"text": text, "audio_url": None}
                continue
            try:
                translations[tgt] = {"text": self.mt.translate(text, detected, tgt), "audio_url": None}
            except Exception as e:
                log.warning("MT %s->%s failed: %s", detected, tgt, e)
        mt_ms = ms_since(t0)

        # ---- TTS (only when a listener needs audio; never fails the request)
        tts_ms = 0
        if want_audio and translations:
            t0 = time.perf_counter()
            for lang, tr in translations.items():
                try:
                    tr["audio_url"] = self._save_wav(self.tts.synthesize(tr["text"], lang))
                except Exception as e:
                    log.warning("TTS %s failed: %s", lang, e)
            tts_ms = ms_since(t0)

        return {"detected_lang": detected, "source_text": text, "translations": translations,
                "timings_ms": {"asr": asr_ms, "mt": mt_ms, "tts": tts_ms}}


KEEP_PREFIXES = ("sample", "mock_")


def cleanup_old_audio(audio_dir: Path, max_age_s: float = 600, now: Optional[float] = None) -> int:
    """Delete generated WAVs older than max_age_s (keeps sample.wav and mock_*.wav). Returns how many were deleted."""
    now = time.time() if now is None else now
    deleted = 0
    for p in Path(audio_dir).glob("*.wav"):
        if p.name.startswith(KEEP_PREFIXES):
            continue
        try:
            if now - p.stat().st_mtime > max_age_s:
                p.unlink()
                deleted += 1
        except OSError:
            pass
    return deleted
