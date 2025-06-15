from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

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
    APP_HOST: str = "8dcf-2409-40d0-1c-503f-4415-7b7a-6aec-63de.ngrok-free.app"  # Your ngrok URL
    app_port: int = 8000
    debug: bool = True
    is_test_environment: bool = False  # Set to False since we're using ngrok
    
    # Conversation Settings
    max_conversation_turns: int = 5
    silence_threshold: float = 0.5  # seconds
    response_timeout: float = 10.0  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()