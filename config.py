from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic import Field

class Settings(BaseSettings):
    """
    Application configuration managed via environment variables and .env file.
    """
    # Twilio settings
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio Account SID")
    TWILIO_AUTH_TOKEN: str = Field(..., description="Twilio Auth Token")
    TWILIO_PHONE_NUMBER: str = Field(..., description="Twilio Phone Number")
    
    # LiveKit settings
    LIVEKIT_API_KEY: str = Field(..., description="LiveKit API Key")
    LIVEKIT_API_SECRET: str = Field(..., description="LiveKit API Secret")
    LIVEKIT_URL: str = Field(..., description="LiveKit Server URL")
    
    # Deepgram settings
    DEEPGRAM_API_KEY: str = Field(..., description="Deepgram API Key")
    
    # Groq settings
    GROQ_API_KEY: str = Field(..., description="Groq API Key")
    GROQ_MODEL: str = Field("mixtral-8x7b-32768", description="Groq Model")
    
    # ElevenLabs settings
    ELEVENLABS_API_KEY: str = Field(..., description="ElevenLabs API Key")
    ELEVENLABS_VOICE_ID: str = Field("21m00Tcm4TlvDq8ikWAM", description="Default ElevenLabs Voice ID (Rachel)")
    
    # Application settings
    APP_HOST: str = Field("localhost", description="Application Host")
    APP_PORT: int = Field(8000, description="Application Port")
    DEBUG: bool = Field(False, description="Debug Mode")
    IS_TEST_ENVIRONMENT: bool = Field(True, description="Is Test Environment")
    
    # Conversation Settings
    MAX_CONVERSATION_TURNS: int = Field(5, description="Max Conversation Turns")
    SILENCE_THRESHOLD: float = Field(0.5, description="Silence Threshold (seconds)")
    RESPONSE_TIMEOUT: float = Field(10.0, description="Response Timeout (seconds)")

    def update_app_host(self, new_host: str):
        """
        Update the APP_HOST value and clear cached settings.
        """
        object.__setattr__(self, "APP_HOST", new_host)
        get_settings.cache_clear()

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of Settings.
    """
    return Settings()
