"""Whisper model wrapper using faster-whisper."""
import os
import numpy as np
from pathlib import Path
from typing import Optional, Iterator
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """Result of transcription."""
    text: str
    start: float
    end: float


# Common Whisper hallucination phrases that appear when there's no real speech
# Multi-word hallucination phrases Whisper produces on silence/noise.
# Deliberately excludes short real words like 'you', 'bye', 'hello'.
HALLUCINATION_PATTERNS = [
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "subscribe to the channel",
    "like and subscribe",
    "the end",
    "thank you",
    "thanks for listening",
]


class WhisperModel:
    """Wrapper for faster-whisper model."""
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        download_root: Optional[str] = None
    ):
        """Initialize Whisper model.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v1/v2/v3)
            device: Device to use (cpu, cuda, auto)
            compute_type: Compute precision (int8, float16, float32)
            download_root: Directory to download/store models
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._load_lock = __import__('threading').Lock()

        # Set default download location
        if download_root is None:
            self.download_root = str(Path.home() / ".cache" / "whisper-stt" / "models")
        else:
            self.download_root = download_root

        os.makedirs(self.download_root, exist_ok=True)

    def _load_model(self):
        """Lazy load the model — thread-safe, loads exactly once."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:  # another thread loaded it while we waited
                return
            try:
                from faster_whisper import WhisperModel as FWModel

                if self.device == "auto":
                    try:
                        import ctranslate2
                        cuda_count = ctranslate2.get_cuda_device_count()
                        self.device = "cuda" if cuda_count > 0 else "cpu"
                    except Exception:
                        self.device = "cpu"

                import os
                cpu_threads = os.cpu_count() or 4
                print(f"Loading Whisper model: {self.model_size} on {self.device} ({cpu_threads} threads)")
                self._model = FWModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=self.download_root,
                    cpu_threads=cpu_threads,
                    num_workers=1,
                )
                print("Model loaded successfully!")
            except ImportError:
                raise ImportError("faster-whisper not installed. Run: pip install faster-whisper")
            except Exception as e:
                raise RuntimeError(f"Failed to load model: {e}")
    
    @staticmethod
    def _is_hallucination(text: str) -> bool:
        """Check if transcribed text is a known Whisper hallucination.
        
        Whisper tends to hallucinate specific phrases when fed silence
        or very quiet audio. This filters those out.
        
        Args:
            text: Transcribed text to check
            
        Returns:
            True if the text appears to be a hallucination
        """
        cleaned = text.strip().lower().rstrip('.!?,')
        
        # Check exact matches against known hallucinations
        if cleaned in HALLUCINATION_PATTERNS:
            return True
        
        # Check for excessive repetition (e.g., "I'm sorry" repeated 50 times)
        words = cleaned.split()
        if len(words) >= 6:
            # Check if any short phrase repeats more than 3 times
            for phrase_len in range(1, 4):
                if len(words) >= phrase_len * 4:
                    phrase = " ".join(words[:phrase_len])
                    count = 0
                    for i in range(0, len(words) - phrase_len + 1, phrase_len):
                        chunk = " ".join(words[i:i + phrase_len])
                        if chunk == phrase:
                            count += 1
                    if count >= 4:
                        return True
        
        return False
    
    @staticmethod
    def _audio_has_speech(audio: np.ndarray, sample_rate: int = 16000) -> bool:
        """Check if audio contains enough energy to likely have speech.
        
        Args:
            audio: Audio array (float32)
            sample_rate: Sample rate
            
        Returns:
            True if audio likely contains speech
        """
        if len(audio) == 0:
            return False
        
        # Check duration - less than 0.3s is too short for meaningful speech
        duration = len(audio) / sample_rate
        if duration < 0.3:
            return False
        
        # Check RMS energy level — threshold lowered to 0.0005 so quiet
        # microphones still pass; Whisper's VAD does the real silence filtering
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 0.0005:
            return False

        # Check peak amplitude
        peak = np.max(np.abs(audio))
        if peak < 0.005:
            return False
        
        return True
    
    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "en",
        beam_size: int = 5,
        best_of: int = 5,
        patience: float = 1.0,
        length_penalty: float = 1.0,
        temperature: float = 0.0,
        compression_ratio_threshold: float = 2.4,
        log_prob_threshold: float = -1.0,
        no_speech_threshold: float = 0.6,
        condition_on_previous_text: bool = False,
        initial_prompt: Optional[str] = None,
        vad_filter: bool = True,
    ) -> Iterator[TranscriptionResult]:
        """Transcribe audio to text.
        
        Args:
            audio: Audio array (float32, 16kHz)
            language: Language code (e.g., 'en', 'es', 'fr')
            beam_size: Beam size for decoding
            best_of: Number of candidates when sampling
            patience: Beam search patience factor
            length_penalty: Length penalty factor
            temperature: Sampling temperature
            compression_ratio_threshold: Compression ratio threshold
            log_prob_threshold: Log probability threshold
            no_speech_threshold: No-speech probability threshold
            condition_on_previous_text: Condition on previous text (False to prevent hallucination loops)
            initial_prompt: Optional initial prompt
            vad_filter: Enable Voice Activity Detection to filter silence
            
        Yields:
            TranscriptionResult objects
        """
        self._load_model()
        
        if len(audio) == 0:
            return
        
        # Ensure audio is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Pre-check: does the audio actually contain speech-level energy?
        if not self._audio_has_speech(audio):
            print("⏭️ Audio too quiet or too short — skipping transcription")
            return
        
        # VAD filter parameters for Silero VAD (used by faster-whisper)
        vad_parameters = None
        if vad_filter:
            vad_parameters = dict(
                threshold=0.25,             # Speech probability threshold (lower = more sensitive)
                min_speech_duration_ms=100,  # Minimum speech segment duration
                max_speech_duration_s=float("inf"),
                min_silence_duration_ms=300,  # Silence to split segments
                speech_pad_ms=200,           # Padding around speech segments
            )
        
        try:
            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=beam_size,
                best_of=best_of,
                patience=patience,
                length_penalty=length_penalty,
                temperature=temperature,
                compression_ratio_threshold=compression_ratio_threshold,
                log_prob_threshold=log_prob_threshold,
                no_speech_threshold=no_speech_threshold,
                condition_on_previous_text=condition_on_previous_text,
                initial_prompt=initial_prompt,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters,
            )
        except Exception as e:
            # If VAD fails (e.g., onnxruntime issue), retry without VAD
            print(f"⚠️ VAD filter failed ({e}), retrying without VAD...")
            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=beam_size,
                best_of=best_of,
                patience=patience,
                length_penalty=length_penalty,
                temperature=temperature,
                compression_ratio_threshold=compression_ratio_threshold,
                log_prob_threshold=log_prob_threshold,
                no_speech_threshold=no_speech_threshold,
                condition_on_previous_text=condition_on_previous_text,
                initial_prompt=initial_prompt,
                vad_filter=False,
            )
        
        print(f"   Language: {info.language} (prob: {info.language_probability:.2f})")
        
        found_segments = False
        for segment in segments:
            text = segment.text.strip()
            
            if not text:
                continue
            
            # Skip hallucinated segments
            if self._is_hallucination(text):
                print(f"⏭️ Filtered hallucination: '{text[:60]}'")
                continue
            
            found_segments = True
            yield TranscriptionResult(
                text=text,
                start=segment.start,
                end=segment.end
            )
        
        if not found_segments:
            print("   No speech segments found by model")
    
    def transcribe_sync(
        self,
        audio: np.ndarray,
        language: str = "en",
        **kwargs
    ) -> str:
        """Transcribe audio and return full text.
        
        Args:
            audio: Audio array
            language: Language code
            **kwargs: Additional transcription options
            
        Returns:
            Transcribed text
        """
        segments = list(self.transcribe(audio, language=language, **kwargs))
        return " ".join(s.text for s in segments).strip()
