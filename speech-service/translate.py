"""
Machine Translation Module (AI4Bharat IndicTrans2) - Role 3 Step 3
Implements Section A6 of shared/CONTRACT.md:
- Distilled 200M IndicTrans2 models:
  - ai4bharat/indictrans2-en-indic-dist-200M
  - ai4bharat/indictrans2-indic-en-dist-200M
- Translates between English, Hindi, Kannada (extendable to ta, te, ml, mr)
- Pivots through English when neither source nor target is English (Indic -> English -> Indic)
- Returns text unchanged when src == tgt
- Caches loaded models
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger("speech-service.translate")

# FLORES-200 language code mapping required by IndicTrans2
INDICTRANS2_LANG_CODES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "kn": "kan_Knda",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
}

EN_INDIC_MODEL_ID = "ai4bharat/indictrans2-en-indic-dist-200M"
INDIC_EN_MODEL_ID = "ai4bharat/indictrans2-indic-en-dist-200M"


class IndicTranslator:
    def __init__(self, device: Optional[str] = None):
        if device is None:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.en_indic_model = None
        self.en_indic_tokenizer = None
        self.indic_en_model = None
        self.indic_en_tokenizer = None

    def load_en_indic(self):
        """Loads English -> Indic model."""
        if self.en_indic_model is not None:
            return
        logger.info(f"Loading {EN_INDIC_MODEL_ID} on {self.device}...")
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch

            self.en_indic_tokenizer = AutoTokenizer.from_pretrained(
                EN_INDIC_MODEL_ID, trust_remote_code=True
            )
            self.en_indic_model = AutoModelForSeq2SeqLM.from_pretrained(
                EN_INDIC_MODEL_ID,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            ).to(self.device)
            self.en_indic_model.eval()
            logger.info("En->Indic model loaded.")
        except Exception as e:
            logger.error(f"Failed to load En->Indic model: {e}")
            raise

    def load_indic_en(self):
        """Loads Indic -> English model."""
        if self.indic_en_model is not None:
            return
        logger.info(f"Loading {INDIC_EN_MODEL_ID} on {self.device}...")
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch

            self.indic_en_tokenizer = AutoTokenizer.from_pretrained(
                INDIC_EN_MODEL_ID, trust_remote_code=True
            )
            self.indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(
                INDIC_EN_MODEL_ID,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            ).to(self.device)
            self.indic_en_model.eval()
            logger.info("Indic->En model loaded.")
        except Exception as e:
            logger.error(f"Failed to load Indic->En model: {e}")
            raise

    def _translate_direct(self, text: str, src_tag: str, tgt_tag: str, is_en_to_indic: bool) -> str:
        """Translates a single text segment using the appropriate model."""
        tokenizer = self.en_indic_tokenizer if is_en_to_indic else self.indic_en_tokenizer
        model = self.en_indic_model if is_en_to_indic else self.indic_en_model

        if tokenizer is None or model is None:
            if is_en_to_indic:
                self.load_en_indic()
                tokenizer = self.en_indic_tokenizer
                model = self.en_indic_model
            else:
                self.load_indic_en()
                tokenizer = self.indic_en_tokenizer
                model = self.indic_en_model

        try:
            import torch

            # Format input with language tags
            inputs = tokenizer(
                [text],
                src_lang=src_tag,
                tgt_lang=tgt_tag,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=256,
            ).to(self.device)

            with torch.no_grad():
                generated_tokens = model.generate(
                    **inputs,
                    num_beams=2,
                    max_length=256,
                )

            decoded = tokenizer.batch_decode(
                generated_tokens,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )
            return decoded[0].strip() if decoded else text

        except Exception as e:
            logger.error(f"Translation execution failed: {e}")
            return text

    def translate(self, text: str, src: str, tgt: str) -> str:
        """
        Translates text from src language code to tgt language code.
        Pivots via English if neither src nor tgt is English.
        """
        if not text or not text.strip():
            return ""

        src_clean = src.lower().strip()
        tgt_clean = tgt.lower().strip()

        # Same language: return text unchanged
        if src_clean == tgt_clean:
            return text

        src_tag = INDICTRANS2_LANG_CODES.get(src_clean)
        tgt_tag = INDICTRANS2_LANG_CODES.get(tgt_clean)

        if not src_tag or not tgt_tag:
            logger.warning(f"Unsupported language pair: {src} -> {tgt}")
            return text

        # English to Indic
        if src_clean == "en":
            return self._translate_direct(text, src_tag, tgt_tag, is_en_to_indic=True)

        # Indic to English
        if tgt_clean == "en":
            return self._translate_direct(text, src_tag, tgt_tag, is_en_to_indic=False)

        # Indic to Indic (Pivot through English)
        en_intermediate = self._translate_direct(
            text, src_tag, INDICTRANS2_LANG_CODES["en"], is_en_to_indic=False
        )
        return self._translate_direct(
            en_intermediate, INDICTRANS2_LANG_CODES["en"], tgt_tag, is_en_to_indic=True
        )
