"""Audio capture from microphone using sounddevice."""
import queue
import threading
import time
import numpy as np
import sounddevice as sd
from typing import Optional


class AudioCapture:
    """Capture audio from microphone in real-time."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """Initialize audio capture.

        Args:
            sample_rate: Audio sample rate (16kHz for Whisper)
            channels: Number of audio channels (1 for mono)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue = queue.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._lock = threading.Lock()
        self._chunks: list = []
        self._chunks_lock = threading.Lock()
        
    def _callback(self, indata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags):
        """Called for each audio chunk."""
        if status:
            print(f"Audio callback status: {status}")
        if self._is_recording:
            chunk = indata.copy()
            self._queue.put(chunk)
            with self._chunks_lock:
                self._chunks.append(chunk)
    
    def start_recording(self) -> None:
        """Start recording from microphone."""
        with self._lock:
            if self._is_recording:
                return
            
            # Clear any existing audio
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            with self._chunks_lock:
                self._chunks = []

            self._is_recording = True
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                callback=self._callback,
                # 'high' latency gives PortAudio a bigger internal buffer so the
                # Python callback has more slack before the ring buffer overflows
                # (seen as "input overflow" warnings on Bluetooth/USB mics).
                latency='high',
            )
            self._stream.start()
    
    def stop_recording(self) -> np.ndarray:
        """Stop recording and return audio data.
        
        Returns:
            Numpy array of audio samples
        """
        with self._lock:
            if not self._is_recording:
                return np.array([], dtype=np.float32)
            
            self._is_recording = False
            if self._stream:
                try:
                    self._stream.stop()
                    time.sleep(0.05)
                    self._stream.close()
                except Exception as e:
                    print(f"Audio stream error: {e}")
                finally:
                    self._stream = None  # always clear so next recording starts clean

            # Collect all audio chunks
            chunks = []
            while not self._queue.empty():
                try:
                    chunks.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            
            if not chunks:
                return np.array([], dtype=np.float32)
            
            # Concatenate all chunks
            return np.concatenate(chunks, axis=0).flatten()
    
    def peek_audio(self) -> np.ndarray:
        """Return all buffered audio so far without clearing the buffer."""
        with self._chunks_lock:
            if not self._chunks:
                return np.array([], dtype=np.float32)
            return np.concatenate(self._chunks, axis=0).flatten()

    def get_new_audio_since(self, chunk_index: int):
        """Return (audio, new_chunk_index) for chunks after chunk_index.

        The caller advances its own index each call to get only new audio.
        """
        with self._chunks_lock:
            new_chunks = self._chunks[chunk_index:]
            new_index = len(self._chunks)
        if not new_chunks:
            return np.array([], dtype=np.float32), chunk_index
        return np.concatenate(new_chunks, axis=0).flatten(), new_index

    def get_audio_from(self, chunk_index: int) -> np.ndarray:
        """Return audio from chunk_index to end — the un-typed remainder."""
        with self._chunks_lock:
            chunks = self._chunks[chunk_index:]
        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks, axis=0).flatten()

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording
