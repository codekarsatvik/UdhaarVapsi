from elevenlabs import generate, set_api_key
import logging
from typing import Optional
import io

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        set_api_key(api_key)
        self.voice_id = voice_id

    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech using ElevenLabs
        """
        try:
            audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            
            logger.info(f"Generated speech for text: {text[:100]}...")
            return audio
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