from elevenlabs import generate, set_api_key
import logging
from typing import Optional
import io
import soundfile as sf
import numpy as np
import tempfile

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        set_api_key(api_key)
        self.voice_id = voice_id

    def _convert_mp3_to_pcm(self, mp3_data: bytes) -> bytes:
        """
        Convert MP3 data to PCM format using soundfile
        """
        try:
            # Create a temporary file to store the MP3 data
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_mp3:
                temp_mp3.write(mp3_data)
                temp_mp3_path = temp_mp3.name

            # Read the audio data using soundfile
            data, samplerate = sf.read(temp_mp3_path)
            
            # Ensure mono audio
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            
            # Resample to 48kHz if needed
            if samplerate != 48000:
                from scipy import signal
                samples = len(data)
                new_samples = int(samples * 48000 / samplerate)
                data = signal.resample(data, new_samples)
            
            # Normalize and convert to 16-bit PCM
            data = np.clip(data, -1.0, 1.0)
            pcm_data = (data * 32767).astype(np.int16).tobytes()
            
            # Log conversion details
            logger.debug(f"Converted audio: {len(pcm_data)} bytes, original samplerate: {samplerate}Hz")
            
            # Clean up the temporary file
            import os
            os.unlink(temp_mp3_path)
            
            return pcm_data
        except Exception as e:
            logger.error(f"Error converting MP3 to PCM: {str(e)}", exc_info=True)
            raise

    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech using ElevenLabs and convert to PCM format
        """
        try:
            # Generate MP3 audio
            mp3_audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            
            # Convert MP3 to PCM
            pcm_audio = self._convert_mp3_to_pcm(mp3_audio)
            
            logger.info(f"Generated and converted speech for text: {text[:100]}...")
            return pcm_audio
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            raise

    async def get_available_voices(self) -> list[dict]:
        """
        Get list of available voices
        """
        try:
            from elevenlabs import voices
            available_voices = voices()
            return [
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category
                }
                for voice in available_voices
            ]
        except Exception as e:
            logger.error(f"Error getting available voices: {str(e)}")
            raise

    def set_voice(self, voice_id: str) -> None:
        """
        Set a different voice for text-to-speech
        """
        try:
            self.voice_id = voice_id
            logger.info(f"Set voice to: {voice_id}")
        except Exception as e:
            logger.error(f"Error setting voice: {str(e)}")
            raise

    def update_voice_settings(
        self,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        style: Optional[float] = None,
        use_speaker_boost: Optional[bool] = None
    ) -> None:
        """
        Update voice settings
        """
        try:
            # This method is no longer applicable with the new initialization
            logger.info("This method is no longer applicable with the new initialization")
        except Exception as e:
            logger.error(f"Error updating voice settings: {str(e)}")
            raise 