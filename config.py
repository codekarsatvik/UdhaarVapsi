from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    
    # LiveKit Configuration
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str
    LIVEKIT_URL: str
    
    # Deepgram Configuration
    DEEPGRAM_API_KEY: str
    
    # Groq Configuration
    GROQ_API_KEY: str
    GROQ_MODEL: str  # Model will be read from environment variable
    
    # ElevenLabs Configuration
    ELEVENLABS_API_KEY: str
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel - most natural voice
    
    # Application Configuration
    APP_HOST: str = "localhost:8000"  # Default value
    app_port: int = 8000
    debug: bool = True
    is_test_environment: bool = False
    
    # Conversation Settings
    max_conversation_turns: int = 5
    silence_threshold: float = 0.5  # seconds
    response_timeout: float = 10.0  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True

    def update_app_host(self, new_host: str):
        """Update the APP_HOST value"""
        self.APP_HOST = new_host
        # Update environment variable to persist the change
        os.environ["APP_HOST"] = new_host

# Create a global settings instance
_settings = Settings()

def get_settings() -> Settings:
    """Get the current settings instance"""
    return _settings

def update_app_host(new_host: str):
    """Update the APP_HOST in the global settings instance"""
    _settings.update_app_host(new_host)