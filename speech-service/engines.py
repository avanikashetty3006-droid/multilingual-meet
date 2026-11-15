"""Real ML engines (MOCK=0). Heavy libraries are imported lazily so MOCK=1 and the unit tests need none of them.

Defaults are CPU friendly and work on Windows:
  ASR  faster-whisper (CTranslate2, int8)           env WHISPER_MODEL=base|small   (default: base)
  MT   NLLB-200 distilled 600M via CTranslate2 int8 env NLLB_CT2_DIR=<converted model folder>
  TTS  facebook/mms-tts-<lang> (VITS, via transformers + torch)
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from audio_io import encode_wav
from langs import MMS, NLLB, WHISPER

log = logging.getLogger("speech-engines")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
NLLB_TOKENIZER = os.getenv("NLLB_TOKENIZER", "facebook/nllb-200-distilled-600M")
NLLB_CT2_DIR = os.getenv("NLLB_CT2_DIR", str(Path(__file__).parent / "models" / "nllb-600m-ct2"))
MT_BEAM = int(os.getenv("MT_BEAM", "2"))
THREADS = int(os.getenv("CPU_THREADS", "0"))  # 0 = library default


def pick_device() -> str:
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class WhisperASR:
    def __init__(self, model_name: str = WHISPER_MODEL, device: str = "cpu"):
        from faster_whisper import WhisperModel  # type: ignore
        compute = "int8" if device == "cpu" else "float16"
        log.info("loading faster-whisper %s on %s (%s)", model_name, device, compute)
        self.model = WhisperModel(model_name, device=device, compute_type=compute, cpu_threads=THREADS)

    def transcribe(self, samples: np.ndarray, language: Optional[str], prev_text: Optional[str]) -> Tuple[List[dict], Optional[str]]:
        segs, info = self.model.transcribe(
            samples,
            language=WHISPER.get(language) if language else None,
            beam_size=1,
            vad_filter=False,                      # the call server already cut the speech
            initial_prompt=prev_text or None,
            condition_on_previous_text=False,
        )
        out = [{"text": s.text, "no_speech_prob": s.no_speech_prob, "avg_logprob": s.avg_logprob} for s in segs]
        detected = info.language if info.language in WHISPER else None
        return out, detected


class NllbMT:
    def __init__(self, ct2_dir: str = NLLB_CT2_DIR, tokenizer_name: str = NLLB_TOKENIZER, device: str = "cpu"):
        import ctranslate2  # type: ignore
        from transformers import AutoTokenizer  # type: ignore
        if not Path(ct2_dir).exists():
            raise FileNotFoundError(
                f"NLLB model folder not found: {ct2_dir}. Convert it once with scripts/convert_nllb.ps1 "
                "(see README) or set NLLB_CT2_DIR.")
        log.info("loading NLLB CT2 model from %s", ct2_dir)
        self.translator = ctranslate2.Translator(ct2_dir, device=device, compute_type="int8",
                                                 inter_threads=1, intra_threads=THREADS)
        self.tokenizer_name = tokenizer_name
        self._tok = {}
        self._AutoTokenizer = AutoTokenizer

    def _tokenizer(self, src_code: str):
        if src_code not in self._tok:
            self._tok[src_code] = self._AutoTokenizer.from_pretrained(self.tokenizer_name, src_lang=src_code)
        return self._tok[src_code]

    def translate(self, text: str, src: str, tgt: str) -> str:
        if src not in NLLB or tgt not in NLLB:
            raise ValueError(f"unsupported language pair {src}->{tgt}")
        tok = self._tokenizer(NLLB[src])
        tokens = tok.convert_ids_to_tokens(tok.encode(text))
        res = self.translator.translate_batch([tokens], target_prefix=[[NLLB[tgt]]], beam_size=MT_BEAM,
                                              max_decoding_length=256)
        out = res[0].hypotheses[0][1:]  # first token is the target language tag
        return tok.decode(tok.convert_tokens_to_ids(out), skip_special_tokens=True).strip()


class MmsTTS:
    """facebook/mms-tts-<lang>: one small VITS model per language, loaded on first use and cached."""

    def __init__(self, device: str = "cpu"):
        import torch  # type: ignore
        from transformers import AutoTokenizer, VitsModel  # type: ignore
        self.torch, self.AutoTokenizer, self.VitsModel, self.device = torch, AutoTokenizer, VitsModel, device
        self._models = {}

    def _load(self, lang: str):
        if lang not in self._models:
            if lang not in MMS:
                raise ValueError(f"no TTS voice for {lang}")
            name = f"facebook/mms-tts-{MMS[lang]}"
            log.info("loading TTS voice %s", name)
            self._models[lang] = (self.VitsModel.from_pretrained(name).to(self.device).eval(),
                                  self.AutoTokenizer.from_pretrained(name))
        return self._models[lang]

    def synthesize(self, text: str, lang: str) -> bytes:
        model, tok = self._load(lang)
        inputs = tok(text, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            wave = model(**inputs).waveform[0].cpu().numpy().astype(np.float32)
        return encode_wav(wave, int(model.config.sampling_rate))


def load_real_pipeline_parts(preload_voices=("hi", "kn")):
    """Load all three engines. Raises if something is missing (main.py reports that instead of crashing)."""
    device = pick_device()
    asr = WhisperASR(device=device)
    mt = NllbMT(device=device)
    tts = MmsTTS(device=device)
    for lang in preload_voices:   # warm the most used voices so the first request is not slow
        try:
            tts._load(lang)
        except Exception as e:
            log.warning("could not preload TTS voice %s: %s", lang, e)
    return asr, mt, tts, device
