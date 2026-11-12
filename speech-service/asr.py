"""
ASR Module (faster-whisper) - Role 3 Step 2
"""
import logging

logger = logging.getLogger("speech-service.asr")

class ASRModel:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def load(self):
        logger.info(f"Loading faster-whisper ({self.model_size}, {self.device}, {self.compute_type})...")
        # Real model loading in Step 2:
        # from faster_whisper import WhisperModel
        # self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        pass

    def transcribe(self, audio_path: str, src_lang: str = "auto"):
        raise NotImplementedError("Real ASR pipeline available in Step 2. Run with MOCK=1.")
