from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Twilio settings
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    
    # LiveKit settings
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str
    LIVEKIT_URL: str
    
    # Deepgram settings
    DEEPGRAM_API_KEY: str
    
    # Groq settings
    GROQ_API_KEY: str
    GROQ_MODEL: str = "mixtral-8x7b-32768"
    
    # ElevenLabs settings
    ELEVENLABS_API_KEY: str
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    
    # Application settings
    APP_HOST: str = "localhost"  # Your application host
    app_port: int = 8000
    debug: bool = False
    is_test_environment: bool = True  # Set to False for production
    
    # Conversation Settings
    max_conversation_turns: int = 5
    silence_threshold: float = 0.5  # seconds
    response_timeout: float = 10.0  # seconds

    def update_app_host(self, new_host: str):
        """Update the APP_HOST value"""
        self.APP_HOST = new_host
        # Clear the cache to force a reload of settings
        get_settings.cache_clear()

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()