"""Real ML engines (MOCK=0). Heavy libraries are imported lazily so MOCK=1 and the unit tests need none of them.

Choose engines with environment variables (all CPU friendly, Windows friendly):
  ASR  faster-whisper (CTranslate2, int8)             WHISPER_MODEL=base|small        (default base)
  MT   MT_ENGINE=indictrans2 (default) | nllb
         indictrans2 : AI4Bharat IndicTrans2 distilled 200M, English pivot for Indic<->Indic. Needs a Hugging Face
                       login (gated models): `huggingface-cli login` and accept the terms on both model pages.
         nllb        : NLLB-200 distilled 600M via CTranslate2 int8 (no login; convert once, NLLB_CT2_DIR)
  TTS  TTS_ENGINE=mms,gtts (default) : engines are tried in this order per sentence
         mms  : facebook/mms-tts-<lang> (offline, WAV)
         gtts : Google gTTS (needs internet; MP3 is converted to WAV with miniaudio)
There is NO silent fallback to canned sentences or web translators: if a model cannot load, /v1/health shows the
reason and chunks get HTTP 503.
"""
import io
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


class IndicTrans2MT:
    """AI4Bharat IndicTrans2 distilled 200M. en->indic and indic->en models; Indic->Indic pivots through English."""

    EN_INDIC = "ai4bharat/indictrans2-en-indic-dist-200M"
    INDIC_EN = "ai4bharat/indictrans2-indic-en-dist-200M"
    BEAMS = int(os.getenv("MT_BEAM", "2"))

    def __init__(self, device: str = "cpu"):
        import torch  # type: ignore
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore
        try:
            from IndicTransToolkit.processor import IndicProcessor  # type: ignore
        except ImportError:
            from IndicTransToolkit import IndicProcessor  # type: ignore
        self.torch, self.device = torch, device
        self.AutoModel, self.AutoTok = AutoModelForSeq2SeqLM, AutoTokenizer
        self.ip = IndicProcessor(inference=True)
        self._models = {}

    def _load(self, name: str):
        if name not in self._models:
            log.info("loading %s (first use downloads about 800 MB)", name)
            tok = self.AutoTok.from_pretrained(name, trust_remote_code=True)
            dtype = self.torch.float16 if self.device == "cuda" else self.torch.float32
            model = self.AutoModel.from_pretrained(name, trust_remote_code=True, torch_dtype=dtype).to(self.device).eval()
            self._models[name] = (model, tok)
        return self._models[name]

    def preload(self):
        self._load(self.EN_INDIC)

    def _direct(self, text: str, src: str, tgt: str) -> str:
        if src not in NLLB or tgt not in NLLB:  # IndicTrans2 uses the same FLORES codes as NLLB
            raise ValueError(f"unsupported language pair {src}->{tgt}")
        model, tok = self._load(self.EN_INDIC if src == "en" else self.INDIC_EN)
        batch = self.ip.preprocess_batch([text], src_lang=NLLB[src], tgt_lang=NLLB[tgt])
        inputs = tok(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True).to(self.device)
        with self.torch.no_grad():
            out = model.generate(**inputs, use_cache=True, min_length=0, max_length=256,
                                 num_beams=self.BEAMS, num_return_sequences=1)
        decoded = tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        return self.ip.postprocess_batch(decoded, lang=NLLB[tgt])[0].strip()

    def translate(self, text: str, src: str, tgt: str) -> str:
        if src == tgt:
            return text
        if src != "en" and tgt != "en":          # Indic -> English -> Indic
            return self._direct(self._direct(text, src, "en"), "en", tgt)
        return self._direct(text, src, tgt)


class GttsTTS:
    """Google gTTS (internet needed). gTTS returns MP3; it is decoded to a 16-bit mono WAV so the file matches contract A6."""

    def __init__(self):
        import gtts  # type: ignore  # noqa: F401
        import miniaudio  # type: ignore  # noqa: F401

    def synthesize(self, text: str, lang: str) -> bytes:
        import miniaudio  # type: ignore
        from gtts import gTTS  # type: ignore
        if lang not in MMS:
            raise ValueError(f"no voice for {lang}")
        buf = io.BytesIO()
        gTTS(text=text, lang=lang, slow=False).write_to_fp(buf)
        dec = miniaudio.decode(buf.getvalue(), output_format=miniaudio.SampleFormat.SIGNED16,
                               nchannels=1, sample_rate=16000)
        samples = np.array(dec.samples, dtype=np.int16).astype(np.float32) / 32768.0
        return encode_wav(samples, 16000)


class ChainTTS:
    """Try several TTS engines in order for each sentence; raise only if all of them fail."""

    def __init__(self, engines: List):
        if not engines:
            raise ValueError("ChainTTS needs at least one engine")
        self.engines = engines

    def synthesize(self, text: str, lang: str) -> bytes:
        last = None
        for e in self.engines:
            try:
                return e.synthesize(text, lang)
            except Exception as ex:  # noqa: BLE001
                last = ex
                log.warning("%s failed for %s: %s", type(e).__name__, lang, ex)
        raise RuntimeError(f"all TTS engines failed: {last}")

    def _load(self, lang: str):   # lets load_real_pipeline_parts warm the offline voices
        for e in self.engines:
            if hasattr(e, "_load"):
                e._load(lang)
                return


def parse_list(value: str) -> List[str]:
    return [x.strip().lower() for x in (value or "").split(",") if x.strip()]


def build_tts(spec: str, device: str):
    """spec like 'mms,gtts'. An engine that cannot be created is skipped with a warning; at least one must work."""
    built, errors = [], []
    for name in parse_list(spec):
        try:
            if name == "mms":
                built.append(MmsTTS(device=device))
            elif name == "gtts":
                built.append(GttsTTS())
            else:
                raise ValueError(f"unknown TTS engine '{name}' (use mms or gtts)")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            log.warning("TTS engine %s unavailable: %s", name, e)
    if not built:
        raise RuntimeError("no TTS engine could be created: " + "; ".join(errors))
    return built[0] if len(built) == 1 else ChainTTS(built)


def build_mt(name: str, device: str):
    name = (name or "indictrans2").strip().lower()
    if name == "indictrans2":
        return IndicTrans2MT(device=device)
    if name == "nllb":
        return NllbMT(device=device)
    raise ValueError(f"unknown MT_ENGINE '{name}' (use indictrans2 or nllb)")


def load_real_pipeline_parts(preload_voices=("hi", "kn")):
    """Load all three engines. Raises if something is missing (main.py reports that instead of crashing)."""
    device = pick_device()
    asr = WhisperASR(device=device)
    mt = build_mt(os.getenv("MT_ENGINE", "indictrans2"), device)
    if hasattr(mt, "preload"):
        mt.preload()
    tts = build_tts(os.getenv("TTS_ENGINE", "mms,gtts"), device)
    for lang in preload_voices:   # warm the most used voices so the first request is not slow
        try:
            tts._load(lang)
        except Exception as e:
            log.warning("could not preload TTS voice %s: %s", lang, e)
    return asr, mt, tts, device
