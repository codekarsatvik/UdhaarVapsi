from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
from config import get_settings, update_app_host
from services.twilio_service import TwilioService
from services.livekit_service import LiveKitService
from services.stt_service import DeepgramService
from services.llm_service import LLMService
from services.tts_service import ElevenLabsService
from services.audio_service import AudioService
from services.call_service import CallService
from services.websocket_service import WebSocketService
import logging
import sys
import os
import ngrok
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="AI Debt Collection Voice Agent")
settings = get_settings()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
twilio_service = TwilioService(
    account_sid=settings.TWILIO_ACCOUNT_SID,
    auth_token=settings.TWILIO_AUTH_TOKEN,
    phone_number=settings.TWILIO_PHONE_NUMBER,
    app_host=settings.APP_HOST
)

livekit_service = LiveKitService(
    api_key=settings.LIVEKIT_API_KEY,
    api_secret=settings.LIVEKIT_API_SECRET,
    url=settings.LIVEKIT_URL
)

stt_service = DeepgramService(
    api_key=settings.DEEPGRAM_API_KEY
)

llm_service = LLMService(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_MODEL
)

tts_service = ElevenLabsService(
    api_key=settings.ELEVENLABS_API_KEY,
    voice_id=settings.elevenlabs_voice_id
)

audio_service = AudioService()

# Initialize call and WebSocket services
call_service = CallService(twilio_service, livekit_service)
websocket_service = WebSocketService(
    livekit_service=livekit_service,
    stt_service=stt_service,
    llm_service=llm_service,
    tts_service=tts_service,
    audio_service=audio_service,
    livekit_api_key=settings.LIVEKIT_API_KEY,
    livekit_api_secret=settings.LIVEKIT_API_SECRET
)

# Create audio directory if it doesn't exist
AUDIO_DIR = "audio_files"
GREETING_FILE = os.path.join(AUDIO_DIR, "greeting.mp3")
os.makedirs(AUDIO_DIR, exist_ok=True)

def get_ngrok_url():
    """Get the current ngrok URL"""
    try:
        # Get the ngrok API URL
        response = requests.get("http://localhost:4040/api/tunnels")
        if response.status_code == 200:
            tunnels = response.json()["tunnels"]
            if tunnels:
                # Get the HTTPS tunnel URL
                for tunnel in tunnels:
                    if tunnel["proto"] == "https":
                        return tunnel["public_url"].replace("https://", "")
        return None
    except Exception as e:
        logger.error(f"Error getting ngrok URL: {str(e)}")
        return None

@app.on_event("startup")
async def startup_event():
    """Initialize services and generate greeting on startup"""
    # Generate greeting audio
    if not os.path.exists(GREETING_FILE):
        logger.info("Generating greeting audio file...")
        greeting = "Hello, I am your AI debt collection agent. How can I help you today?"
        audio_response = await tts_service.text_to_speech(greeting)
        if audio_response:
            with open(GREETING_FILE, "wb") as f:
                f.write(audio_response)
            logger.info(f"Saved greeting audio to {GREETING_FILE}")

    # Get ngrok URL and update settings
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        logger.info(f"Using ngrok URL: {ngrok_url}")
        update_app_host(ngrok_url)
        twilio_service.update_app_host(ngrok_url)
        logger.info(f"Updated APP_HOST to: {ngrok_url}")
    else:
        logger.warning("Could not detect ngrok URL. Using default APP_HOST")

class CallRequest(BaseModel):
    phone_number: str
    amount: float
    due_date: str
    account_number: Optional[str] = None

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/test")
async def test_interface():
    return FileResponse("static/test.html")

@app.post("/api/call")
async def initiate_call(data: CallRequest):
    return await call_service.initiate_call(
        phone_number=data.phone_number,
        amount=data.amount,
        due_date=data.due_date,
        account_number=data.account_number
    )

@app.post("/twiml/{call_id}")
async def generate_twiml(call_id: str):
    twiml = call_service.generate_twiml(call_id)
    return Response(content=twiml, media_type="application/xml")

@app.websocket("/stream/{call_id}")
async def stream_audio(websocket: WebSocket, call_id: str):
    await websocket_service.handle_stream_connection(websocket, call_id)

@app.websocket("/ws/call/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket_service.handle_client_connection(websocket, call_id)

@app.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        event_type = form_data.get("EventType")
        
        logger.info(f"Received Twilio webhook - CallSid: {call_sid}, EventType: {event_type}")
        logger.info(f"Full webhook data: {dict(form_data)}")
        
        if event_type == "media":
            # Handle incoming audio stream
            audio_data = form_data.get("Media")
            if not audio_data:
                logger.warning("No audio data received in media event")
                return JSONResponse({"status": "error", "message": "No audio data received"})
                
            # Process audio with Deepgram
            transcription = await stt_service.transcribe(audio_data)
            if not transcription:
                logger.warning("No transcription received from Deepgram")
                return JSONResponse({"status": "error", "message": "Transcription failed"})
                
            # Generate response with LLM
            response = await llm_service.generate_response(transcription, call_sid)
            if not response:
                logger.warning("No response generated from LLM")
                return JSONResponse({"status": "error", "message": "Response generation failed"})
                
            # Convert response to speech
            audio_response = await tts_service.text_to_speech(response)
            if not audio_response:
                logger.warning("No audio response generated from TTS")
                return JSONResponse({"status": "error", "message": "TTS failed"})
                
            # Send back through LiveKit
            room_name = f"call-{call_sid}"
            if room_name in livekit_service.audio_tracks:
                track = livekit_service.audio_tracks[room_name]
                await track.write(audio_response)
                logger.info(f"Sent audio response to LiveKit room {room_name}")
            else:
                logger.warning(f"No audio track found for room {room_name}")
            
        return JSONResponse({"status": "success"})
    except Exception as e:
        logger.error(f"Error in Twilio webhook: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/webhook/livekit")
async def livekit_webhook(request: Request):
    try:
        data = await request.json()
        event_type = data.get("event")
        
        if event_type == "room_ended":
            # Handle call end
            room_name = data.get("room")
            await livekit_service.cleanup_room(room_name)
        
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    settings = get_settings()
    
    # Debug logging for settings
    logger.info("="*50)
    logger.info("Current Settings:")
    logger.info(f"APP_HOST: {settings.APP_HOST}")
    logger.info(f"app_port: {settings.app_port}")
    logger.info(f"is_test_environment: {settings.is_test_environment}")
    logger.info("="*50)
    
    if settings.is_test_environment:
        print("\nRunning in TEST environment")
        print("Make sure to:")
        print("1. Use Twilio's test credentials")
        print("2. Configure your Twilio phone number's webhook to:")
        print(f"   - Voice: https://{settings.APP_HOST}/twiml/{{call_id}}")
        print(f"   - Status: https://{settings.APP_HOST}/webhook/twilio")
        print("\nFor production, set is_test_environment=False in .env")
    else:
        print("\nRunning in PRODUCTION environment")
        print(f"Using host: {settings.APP_HOST}")
    
    # Start the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.debug
    ) 