import numpy as np
import wave
import io
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self, audio_dir: str = "audio_files"):
        self.audio_dir = audio_dir
        os.makedirs(audio_dir, exist_ok=True)

    def convert_audio_to_samples(self, audio_data: bytes, sample_rate: int = 16000) -> np.ndarray:
        """Convert audio bytes to numpy array of samples"""
        try:
            # Try to read as WAV first
            with wave.open(io.BytesIO(audio_data), 'rb') as wav_file:
                # Get audio parameters
                n_channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                n_frames = wav_file.getnframes()
                
                # Read frames and convert to numpy array
                frames = wav_file.readframes(n_frames)
                samples = np.frombuffer(frames, dtype=np.int16)
                
                # Reshape if stereo
                if n_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                
                return samples.astype(np.int16)
        except:
            # If not WAV, assume raw PCM
            try:
                # Ensure buffer size is even (2 bytes per sample)
                if len(audio_data) % 2 != 0:
                    audio_data = audio_data[:-1]
                
                samples = np.frombuffer(audio_data, dtype=np.int16)
                return samples.astype(np.int16)
            except Exception as e:
                logger.error(f"Error converting audio to samples: {str(e)}")
                # Return empty array with correct dtype
                return np.array([], dtype=np.int16)

    def save_audio_file(self, audio_data: bytes, call_id: str, file_type: str) -> str:
        """Save audio data to a file with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{call_id}_{file_type}_{timestamp}.{'mp3' if file_type == 'response' else 'wav'}"
        filepath = os.path.join(self.audio_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(audio_data)
        logger.info(f"Saved {file_type} audio to {filepath}")
        
        return filepath 