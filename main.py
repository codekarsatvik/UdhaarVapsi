from fastapi import FastAPI, WebSocket, HTTPException, Request, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
from config import get_settings, Settings
from services.twilio_service import TwilioService
from services.livekit_service import LiveKitService
from services.stt_service import DeepgramService
from services.llm_service import LLMService
from services.tts_service import ElevenLabsService
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
import json
import asyncio
import websockets
import uuid
import logging
import sys
from fastapi import WebSocketDisconnect
import base64
import time
import jwt
from livekit import rtc
import socket
import os
from datetime import datetime
import numpy as np
import wave
import io
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

def get_ngrok_url():
    """Get the current ngrok URL"""
    try:
        # Try to get ngrok URL from the ngrok API
        response = requests.get("http://localhost:4040/api/tunnels")
        if response.status_code == 200:
            tunnels = response.json()["tunnels"]
            for tunnel in tunnels:
                if tunnel["proto"] == "https":
                    return tunnel["public_url"].replace("https://", "")
        return None
    except Exception as e:
        logger.error(f"Error getting ngrok URL: {str(e)}")
        return None

def update_app_host():
    """Update APP_HOST with current ngrok URL"""
    try:
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            # Update the settings
            settings = get_settings()
            settings.update_app_host(ngrok_url)
            logger.info(f"Updated APP_HOST to: {ngrok_url}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating APP_HOST: {str(e)}")
        return False

app = FastAPI(title="AI Debt Collection Voice Agent")
settings = get_settings()

# Update APP_HOST on startup
@app.on_event("startup")
async def startup_event():
    """Update APP_HOST with ngrok URL on startup"""
    if update_app_host():
        logger.info("Successfully updated APP_HOST with ngrok URL")
    else:
        logger.warning("Failed to update APP_HOST with ngrok URL")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
twilio_service = TwilioService(
    account_sid=settings.TWILIO_ACCOUNT_SID,
    auth_token=settings.TWILIO_AUTH_TOKEN,
    phone_number=settings.TWILIO_PHONE_NUMBER
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

# Initialize Twilio client
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, region='us1')

# Create audio directory if it doesn't exist
AUDIO_DIR = "audio_files"
GREETING_FILE = os.path.join(AUDIO_DIR, "greeting.mp3")
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.on_event("startup")
async def generate_greeting():
    """Generate greeting audio file on startup if it doesn't exist"""
    if not os.path.exists(GREETING_FILE):
        logger.info("Generating greeting audio file...")
        greeting = "Hello, I am your AI debt collection agent. How can I help you today?"
        audio_response = await tts_service.text_to_speech(greeting)
        if audio_response:
            with open(GREETING_FILE, "wb") as f:
                f.write(audio_response)
            logger.info(f"Saved greeting audio to {GREETING_FILE}")

def convert_audio_to_samples(audio_data: bytes, sample_rate: int = 16000) -> np.ndarray:
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

class CallRequest(BaseModel):
    phone_number: str
    amount: float
    due_date: str
    account_number: Optional[str] = None

class TestLLMRequest(BaseModel):
    transcript: str

class TestTTSRequest(BaseModel):
    text: str

class STTRequest(BaseModel):
    audio_data: str  # base64 encoded audio data
    file_name: str

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/call")
async def initiate_call(data: CallRequest):
    try:
        # Validate phone number format
        if not data.phone_number.startswith('+'):
            raise HTTPException(status_code=400, detail="Phone number must start with country code (e.g., +91)")

        # Generate a unique call ID
        call_id = str(uuid.uuid4())
        
        # Make the outbound call using Twilio
        try:
            call = twilio_client.calls.create(
                to=data.phone_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=f"https://{settings.APP_HOST}/twiml/{call_id}"
            )
            
            return {"call_id": call_id, "status": "initiated", "twilio_sid": call.sid}
        except Exception as e:
            logger.error(f"Twilio call creation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create call: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in initiate_call: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.post("/twiml/{call_id}")
async def generate_twiml(call_id: str):
    try:
        logger.info(f"Generating TwiML for call {call_id}")
        response = VoiceResponse()
        
        # Create a Connect verb with Stream
        connect = Connect()
        stream_url = f"wss://{settings.APP_HOST}/stream/{call_id}"
        logger.info(f"Using WebSocket URL: {stream_url}")
        connect.stream(url=stream_url)
        response.append(connect)
        
        # Add a fallback message
        response.say("Connecting to the AI agent. Please wait.", voice="Polly.Amy")
        
        logger.info(f"Generated TwiML: {str(response)}")
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error generating TwiML: {str(e)}")
        response = VoiceResponse()
        response.say("An error occurred. Please try again later.", voice="Polly.Amy")
        return Response(content=str(response), media_type="application/xml")

@app.websocket("/stream/{call_id}")
async def stream_audio(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for call {call_id}")
    
    try:
        # Generate LiveKit token
        livekit_token = generate_livekit_token(call_id)
        room_name = f"call-{call_id}"
        
        # Connect to LiveKit
        logger.info(f"Connecting to LiveKit room {room_name}")
        room = rtc.Room()
        
        # Use the LiveKit URL as provided
        ws_url = settings.LIVEKIT_URL
        if not ws_url.endswith('/rtc'):
            ws_url = f"{ws_url}/rtc"
            
        logger.info(f"Connecting to LiveKit at: {ws_url}")
        
        # Create room first
        try:
            await livekit_service.create_room(room_name)
            logger.info(f"Created LiveKit room: {room_name}")
        except Exception as e:
            logger.error(f"Failed to create LiveKit room: {str(e)}")
            raise
        
        # Connect to room
        try:
            await room.connect(ws_url, livekit_token)
            logger.info(f"Connected to LiveKit room {room_name}")
        except Exception as e:
            logger.error(f"Failed to connect to LiveKit room: {str(e)}")
            raise
        
        # Create and publish audio track
        try:
            # Create audio source with required parameters
            audio_source = rtc.AudioSource(
                sample_rate=16000,  # Standard sample rate for telephony
                num_channels=1      # Mono audio for telephony
            )
            
            # Create audio track with source
            audio_track = rtc.LocalAudioTrack.create_audio_track(
                name=f"audio-{call_id}",
                source=audio_source
            )
            logger.info("Created audio track")
            
            await room.local_participant.publish_track(audio_track)
            logger.info(f"Published audio track for room {room_name}")
        except Exception as e:
            logger.error(f"Failed to create/publish audio track: {str(e)}")
            raise
        
        # Send initial greeting
        try:
            # Read greeting from file
            with open(GREETING_FILE, "rb") as f:
                audio_response = f.read()
            
            # Save a copy with timestamp for this call
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            greeting_file = os.path.join(AUDIO_DIR, f"{call_id}_greeting_{timestamp}.mp3")
            with open(greeting_file, "wb") as f:
                f.write(audio_response)
            logger.info(f"Saved greeting audio to {greeting_file}")
            
            # Convert audio to samples and push to source
            samples = convert_audio_to_samples(audio_response)
            audio_source.push_data(samples, sample_rate=16000)
            logger.info("Sent initial greeting")
        except Exception as e:
            logger.error(f"Failed to send greeting: {str(e)}")
            raise
        
        # Handle audio streaming
        while True:
            try:
                data = await websocket.receive_bytes()
                logger.info(f"Received {len(data)} bytes from Twilio")
                
                # Save incoming audio
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                incoming_file = os.path.join(AUDIO_DIR, f"{call_id}_incoming_{timestamp}.wav")
                with open(incoming_file, "wb") as f:
                    f.write(data)
                logger.info(f"Saved incoming audio to {incoming_file}")
                
                # Convert audio to samples and push to source
                samples = convert_audio_to_samples(data)
                audio_source.push_data(samples, sample_rate=16000)
                
                # Process audio with Deepgram
                transcription = await stt_service.transcribe(data)
                if transcription:
                    logger.info(f"Transcription: {transcription}")
                    
                    # Generate response
                    response = await llm_service.generate_response(transcription, call_id)
                    if response:
                        logger.info(f"Generated response: {response}")
                        
                        # Convert to speech and send
                        audio_response = await tts_service.text_to_speech(response)
                        if audio_response:
                            # Save response audio
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            response_file = os.path.join(AUDIO_DIR, f"{call_id}_response_{timestamp}.mp3")
                            with open(response_file, "wb") as f:
                                f.write(audio_response)
                            logger.info(f"Saved response audio to {response_file}")
                            
                            # Convert audio to samples and push to source
                            samples = convert_audio_to_samples(audio_response)
                            audio_source.push_data(samples, sample_rate=16000)
                            logger.info("Sent audio response")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for call {call_id}")
                break
            except Exception as e:
                logger.error(f"Error in audio streaming: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"Error in stream_audio: {str(e)}")
        # Try to clean up
        try:
            await livekit_service.cleanup_room(room_name)
        except:
            pass
    finally:
        try:
            await room.disconnect()
        except:
            pass
        await websocket.close()
        logger.info(f"Cleaned up WebSocket connection for call {call_id}")

@app.websocket("/ws/call/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    
    try:
        # Connect to LiveKit for real-time updates
        livekit_url = settings.LIVEKIT_URL
        livekit_token = generate_livekit_token(call_id)
        
        async with websockets.connect(livekit_url) as ws:
            # Send authentication
            await ws.send(json.dumps({
                "type": "auth",
                "token": livekit_token
            }))
            
            # Forward messages to the client
            while True:
                message = await ws.recv()
                await websocket.send_text(message)
                
    except Exception as e:
        print(f"Error in websocket_endpoint: {e}")
        await websocket.close()

def generate_livekit_token(call_id: str) -> str:
    """
    Generate a LiveKit token for room access
    """
    try:
        now = int(time.time())
        exp = now + 3600  # Token expires in 1 hour

        claims = {
            "iss": settings.LIVEKIT_API_KEY,
            "sub": "agent",
            "exp": exp,
            "nbf": now,
            "room": f"call-{call_id}",
            "metadata": "agent",
            "video": {
                "roomCreate": True,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True
            },
            "audio": {
                "roomCreate": True,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True
            }
        }

        # Ensure the secret is in the correct format
        if isinstance(settings.LIVEKIT_API_SECRET, str):
            secret = settings.LIVEKIT_API_SECRET.encode('utf-8')
        else:
            secret = settings.LIVEKIT_API_SECRET

        token = jwt.encode(claims, secret, algorithm="HS256")
        logger.info(f"Generated LiveKit token for call {call_id}")
        return token
    except Exception as e:
        logger.error(f"Error generating LiveKit token: {str(e)}")
        raise

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

@app.get("/test")
async def test_interface():
    return FileResponse("static/test.html")

@app.websocket("/ws/test")
async def test_websocket(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
        
        while True:
            try:
                # Receive audio data
                audio_data = await websocket.receive_bytes()
                logger.info(f"Received audio data: {len(audio_data)} bytes")
                
                if not audio_data:
                    logger.warning("Empty audio data received")
                    continue
                
                # Log first few bytes for debugging
                logger.debug(f"First 10 bytes of audio data: {audio_data[:10]}")
                
                try:
                    # Transcribe audio
                    logger.info("Sending audio to STT service...")
                    transcript = await stt_service.transcribe(audio_data)
                    logger.info(f"Transcription result: {transcript}")
                    
                    if transcript:
                        # Generate response
                        logger.info("Generating response...")
                        response = await llm_service.generate_response(transcript)
                        logger.info(f"Generated response: {response}")
                        
                        # Convert response to speech
                        logger.info("Converting response to speech...")
                        audio_response = await tts_service.text_to_speech(response)
                        
                        try:
                            # Send transcription and response back to client
                            await websocket.send_json({
                                "type": "transcription",
                                "text": transcript,
                                "speaker": "user"
                            })
                            
                            await websocket.send_json({
                                "type": "response",
                                "text": response,
                                "speaker": "agent"
                            })
                            
                            # Send audio response
                            if audio_response:
                                logger.info(f"Sending audio response: {len(audio_response)} bytes")
                                await websocket.send_bytes(audio_response)
                        except Exception as e:
                            logger.error(f"Error sending response: {str(e)}", exc_info=True)
                            if not isinstance(e, WebSocketDisconnect):
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "Error sending response"
                                })
                            raise
                    else:
                        logger.warning("No transcription result")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Could not transcribe audio"
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing audio: {str(e)}", exc_info=True)
                    if not isinstance(e, WebSocketDisconnect):
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Error processing audio: {str(e)}"
                        })
                    raise
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"Error receiving data: {str(e)}", exc_info=True)
                if not isinstance(e, WebSocketDisconnect):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error receiving data: {str(e)}"
                    })
                raise
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        try:
            if not isinstance(e, WebSocketDisconnect):
                await websocket.send_json({
                    "type": "error",
                    "message": f"Connection error: {str(e)}"
                })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

@app.post("/api/test-call")
async def test_call(data: CallRequest):
    try:
        logger.info(f"Starting test call to {data.phone_number}")
        
        # Validate phone number format
        if not data.phone_number.startswith('+'):
            raise HTTPException(status_code=400, detail="Phone number must start with country code (e.g., +91)")

        # Generate a unique call ID
        call_id = str(uuid.uuid4())
        logger.info(f"Generated call ID: {call_id}")
        
        # Create LiveKit room first
        try:
            logger.info("Creating LiveKit room...")
            room_name = f"call-{call_id}"
            await livekit_service.create_room(room_name)
            logger.info(f"LiveKit room created: {room_name}")
        except Exception as e:
            logger.error(f"Failed to create LiveKit room: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create LiveKit room")
        
        # Construct webhook URLs with HTTPS
        twiml_url = f"https://{settings.APP_HOST}/twiml/{call_id}"
        status_callback_url = f"https://{settings.APP_HOST}/webhook/twilio"
        
        logger.info(f"Using TwiML URL: {twiml_url}")
        logger.info(f"Using Status Callback URL: {status_callback_url}")
        
        # Make the outbound call using Twilio
        try:
            logger.info("Initiating Twilio call...")
            call = twilio_client.calls.create(
                to=data.phone_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=twiml_url,
                status_callback=status_callback_url,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            logger.info(f"Twilio call created with SID: {call.sid}")
            
            return {
                "call_id": call_id,
                "status": "initiated",
                "twilio_sid": call.sid,
                "livekit_room": room_name
            }
            
        except Exception as e:
            logger.error(f"Twilio call creation failed: {str(e)}")
            try:
                await livekit_service.cleanup_room(room_name)
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to create call: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in test_call: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.get("/test-local")
async def test_local():
    """Return the test interface"""
    return FileResponse("static/test.html")

@app.post("/api/test-stt")
async def test_stt(request: STTRequest):
    """Test endpoint for STT"""
    try:
        # Decode base64 audio data
        audio_data = base64.b64decode(request.audio_data)
        
        # Save for debugging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.join(AUDIO_DIR, f"test_stt_{timestamp}.wav")
        with open(debug_file, "wb") as f:
            f.write(audio_data)
        logger.info(f"Saved test audio to {debug_file}")
        
        # Transcribe
        transcript = await stt_service.transcribe(audio_data)
        logger.info(f"Transcription: {transcript}")
        
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Error in test_stt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-llm")
async def test_llm(request: TestLLMRequest):
    try:
        logger.info("Testing Groq LLM...")
        logger.info(f"Input transcript: {request.transcript}")
        
        # Generate a test call ID
        test_call_id = "test-" + str(uuid.uuid4())
        logger.debug(f"Using test call ID: {test_call_id}")
        
        # Generate response
        response = await llm_service.generate_response(request.transcript, test_call_id)
        logger.info(f"LLM response: {response}")
        
        return {
            "status": "success",
            "response": response,
            "call_id": test_call_id
        }
        
    except Exception as e:
        logger.error(f"Error in test_llm: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-tts")
async def test_tts(request: TestTTSRequest):
    try:
        logger.info("Testing ElevenLabs TTS...")
        logger.info(f"Input text: {request.text}")
        
        # Convert text to speech
        audio_data = await tts_service.text_to_speech(request.text)
        logger.info(f"Generated audio: {len(audio_data)} bytes")
        
        # Return audio file
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=response.mp3"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in test_tts: {str(e)}", exc_info=True)
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