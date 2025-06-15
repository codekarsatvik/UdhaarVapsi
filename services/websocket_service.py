import logging
import json
import jwt
import time
from typing import Optional
from fastapi import WebSocket
from livekit import rtc
from datetime import datetime
import websockets
import base64
import os
import numpy as np

logger = logging.getLogger(__name__)

class WebSocketService:
    def __init__(self, livekit_service, stt_service, llm_service, tts_service, audio_service, livekit_api_key: str, livekit_api_secret: str):
        self.livekit_service = livekit_service
        self.stt_service = stt_service
        self.llm_service = llm_service
        self.tts_service = tts_service
        self.audio_service = audio_service
        self.livekit_api_key = livekit_api_key
        self.livekit_api_secret = livekit_api_secret
        self.active_connections: dict = {}
        self.greeting_sent = set()

    def generate_livekit_token(self, call_id: str) -> str:
        """Generate a LiveKit token for room access"""
        try:
            now = int(time.time())
            exp = now + 3600  # Token expires in 1 hour

            claims = {
                "iss": self.livekit_api_key,
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
            if isinstance(self.livekit_api_secret, str):
                secret = self.livekit_api_secret.encode('utf-8')
            else:
                secret = self.livekit_api_secret

            token = jwt.encode(claims, secret, algorithm="HS256")
            logger.info(f"Generated LiveKit token for call {call_id}")
            return token
        except Exception as e:
            logger.error(f"Error generating LiveKit token: {str(e)}")
            raise

    async def send_greeting(self, audio_source, call_id: str):
        """Send initial greeting to the call"""
        if call_id in self.greeting_sent:
            logger.info(f"Greeting already sent for call {call_id}")
            return

        try:
            greeting_file = os.path.join("audio_files", "greeting.mp3")
            logger.info(f"Looking for greeting file at: {os.path.abspath(greeting_file)}")
            
            if not os.path.exists(greeting_file):
                logger.error(f"Greeting file not found at {greeting_file}")
                # Create a default greeting using TTS
                try:
                    greeting_text = "Hello! I am your AI assistant. How can I help you today?"
                    logger.info("Generating greeting using TTS")
                    greeting_audio = await self.tts_service.text_to_speech(greeting_text)
                    if greeting_audio:
                        logger.info(f"Successfully generated greeting audio, size: {len(greeting_audio)} bytes")
                    else:
                        logger.error("Failed to generate greeting audio")
                        return
                except Exception as tts_error:
                    logger.error(f"Error generating greeting with TTS: {str(tts_error)}")
                    return
            else:
                logger.info("Found existing greeting file")
                with open(greeting_file, "rb") as f:
                    greeting_audio = f.read()
                logger.info(f"Read greeting file, size: {len(greeting_audio)} bytes")
            
            if not greeting_audio:
                logger.error("No greeting audio data available")
                return
                
            # Convert greeting audio to samples
            logger.info("Converting greeting audio to samples")
            samples = self.audio_service.convert_audio_to_samples(greeting_audio)
            if samples is not None and len(samples) > 0:
                logger.info(f"Converted greeting audio to {len(samples)} samples")
                # Convert to numpy array and ensure correct format
                samples_array = np.array(samples, dtype=np.float32)
                logger.info(f"Created numpy array with shape: {samples_array.shape}, dtype: {samples_array.dtype}")
                
                # Create audio frame
                try:
                    frame = rtc.AudioFrame(
                        samples_per_channel=len(samples_array),
                        num_channels=1,
                        sample_rate=48000,
                        data=samples_array
                    )
                    logger.info(f"Created AudioFrame with {len(samples_array)} samples per channel")
                    
                    # Push to LiveKit
                    logger.info("Pushing greeting audio to LiveKit")
                    await audio_source.capture_frame(frame)
                    logger.info("Successfully sent greeting audio")
                    self.greeting_sent.add(call_id)
                except Exception as frame_error:
                    logger.error(f"Error creating or sending audio frame: {str(frame_error)}", exc_info=True)
            else:
                logger.error("Failed to convert greeting audio to samples")
        except Exception as e:
            logger.error(f"Error sending greeting: {str(e)}", exc_info=True)

    async def handle_stream_connection(self, websocket: WebSocket, call_id: str):
        """Handle WebSocket connection for audio streaming"""
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call {call_id}")
        
        room = None
        audio_source = None
        audio_track = None
        conversation_data = {
            "incoming_audio": [],
            "responses": [],
            "transcriptions": []
        }
        
        try:
            # Generate LiveKit token
            livekit_token = self.generate_livekit_token(call_id)
            room_name = f"call-{call_id}"
            
            # Connect to LiveKit
            logger.info(f"Connecting to LiveKit room {room_name}")
            room = rtc.Room()
            
            # Use the LiveKit URL as provided
            ws_url = self.livekit_service.url
            if not ws_url.endswith('/rtc'):
                ws_url = f"{ws_url}/rtc"
                
            logger.info(f"Connecting to LiveKit at: {ws_url}")
            
            # Create room first
            try:
                await self.livekit_service.create_room(room_name)
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
                    sample_rate=48000,  # LiveKit's expected sample rate
                    num_channels=1      # Mono audio
                )
                logger.info("Created audio source")
                
                # Create audio track with source
                audio_track = rtc.LocalAudioTrack.create_audio_track(
                    name=f"audio-{call_id}",
                    source=audio_source
                )
                logger.info("Created audio track")
                
                await room.local_participant.publish_track(audio_track)
                logger.info(f"Published audio track for room {room_name}")
                
                # Send greeting
                logger.info("Attempting to send greeting")
                await self.send_greeting(audio_source, call_id)
                logger.info("Greeting process completed")
                
            except Exception as e:
                logger.error(f"Failed to create/publish audio track: {str(e)}")
                raise
            
            # Store connection info
            self.active_connections[call_id] = {
                "websocket": websocket,
                "room": room,
                "audio_source": audio_source,
                "audio_track": audio_track
            }
            
            # Handle audio streaming
            while True:
                try:
                    # Receive message from WebSocket
                    message = await websocket.receive()
                    
                    # Check if it's a disconnect message
                    if message.get("type") == "websocket.disconnect":
                        logger.info("Received disconnect message")
                        break
                        
                    # Handle text messages (media data from Twilio)
                    if "text" in message:
                        try:
                            text_data = message["text"]
                            media_data = json.loads(text_data)
                            
                            if media_data.get("event") == "media":
                                # Decode base64 audio data
                                audio_payload = media_data["media"]["payload"]
                                audio_data = base64.b64decode(audio_payload)
                                
                                # Store incoming audio data
                                conversation_data["incoming_audio"].append(audio_data)
                                
                                # Convert audio to samples and push to source
                                try:
                                    samples = self.audio_service.convert_audio_to_samples(audio_data)
                                    if samples is not None and len(samples) > 0:
                                        # Convert to numpy array and ensure correct format
                                        samples_array = np.array(samples, dtype=np.float32)
                                        # Create audio frame
                                        frame = rtc.AudioFrame(
                                            samples_per_channel=len(samples_array),
                                            num_channels=1,
                                            sample_rate=48000,
                                            data=samples_array
                                        )
                                        await audio_source.capture_frame(frame)
                                except Exception as audio_error:
                                    logger.error(f"Error processing audio data: {str(audio_error)}")
                                    continue
                                
                                # Process audio with Deepgram
                                try:
                                    transcription = await self.stt_service.transcribe(audio_data)
                                    if transcription:
                                        logger.info(f"Transcription: {transcription}")
                                        conversation_data["transcriptions"].append(transcription)
                                        
                                        # Generate response
                                        response = await self.llm_service.generate_response(transcription, call_id)
                                        if response:
                                            logger.info(f"Generated response: {response}")
                                            
                                            # Convert to speech and send
                                            audio_response = await self.tts_service.text_to_speech(response)
                                            if audio_response:
                                                # Store response audio
                                                conversation_data["responses"].append({
                                                    "text": response,
                                                    "audio": audio_response
                                                })
                                                
                                                # Convert audio to samples and push to source
                                                try:
                                                    response_samples = self.audio_service.convert_audio_to_samples(audio_response)
                                                    if response_samples is not None and len(response_samples) > 0:
                                                        # Convert to numpy array and ensure correct format
                                                        response_array = np.array(response_samples, dtype=np.float32)
                                                        # Create audio frame
                                                        response_frame = rtc.AudioFrame(
                                                            samples_per_channel=len(response_array),
                                                            num_channels=1,
                                                            sample_rate=48000,
                                                            data=response_array
                                                        )
                                                        await audio_source.capture_frame(response_frame)
                                                        logger.info("Sent audio response")
                                                except Exception as response_error:
                                                    logger.error(f"Error processing response audio: {str(response_error)}")
                                except Exception as stt_error:
                                    logger.error(f"Error in speech-to-text processing: {str(stt_error)}")
                                    continue
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON message")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing message: {str(e)}")
                            continue
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error in audio streaming: {str(e)}", exc_info=True)
                    break
                    
        except Exception as e:
            logger.error(f"Error in stream_audio: {str(e)}", exc_info=True)
        finally:
            # Save conversation data
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                conversation_file = os.path.join("audio_files", f"{call_id}_conversation_{timestamp}.json")
                
                # Convert binary audio data to base64 for JSON storage
                conversation_json = {
                    "call_id": call_id,
                    "timestamp": timestamp,
                    "transcriptions": conversation_data["transcriptions"],
                    "responses": [
                        {
                            "text": r["text"],
                            "audio": base64.b64encode(r["audio"]).decode('utf-8')
                        }
                        for r in conversation_data["responses"]
                    ],
                    "incoming_audio": [
                        base64.b64encode(audio).decode('utf-8')
                        for audio in conversation_data["incoming_audio"]
                    ]
                }
                
                with open(conversation_file, 'w') as f:
                    json.dump(conversation_json, f)
                logger.info(f"Saved conversation data to {conversation_file}")
            except Exception as e:
                logger.error(f"Error saving conversation data: {str(e)}")
            
            # Clean up resources
            if room:
                try:
                    await room.disconnect()
                    logger.info("Disconnected from LiveKit room")
                except Exception as e:
                    logger.error(f"Error disconnecting from room: {str(e)}")
            
            try:
                await self.livekit_service.cleanup_room(room_name)
                logger.info(f"Cleaned up LiveKit room: {room_name}")
            except Exception as e:
                logger.error(f"Error cleaning up room: {str(e)}")
            
            try:
                await websocket.close()
                logger.info("Closed WebSocket connection")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")
            
            if call_id in self.active_connections:
                del self.active_connections[call_id]
                logger.info(f"Removed connection info for call {call_id}")
            
            logger.info(f"Completed cleanup for call {call_id}")

    async def handle_client_connection(self, websocket: WebSocket, call_id: str):
        """Handle WebSocket connection for client updates"""
        await websocket.accept()
        logger.info(f"Client WebSocket connection accepted for call {call_id}")
        
        try:
            # Connect to LiveKit for real-time updates
            livekit_url = self.livekit_service.url
            if not livekit_url.endswith('/rtc'):
                livekit_url = f"{livekit_url}/rtc"
            
            livekit_token = self.generate_livekit_token(call_id)
            logger.info(f"Connecting to LiveKit at {livekit_url}")
            
            # Add authentication headers
            headers = {
                "Authorization": f"Bearer {livekit_token}",
                "Sec-WebSocket-Protocol": "livekit"
            }
            
            async with websockets.connect(
                livekit_url,
                extra_headers=headers,
                subprotocols=["livekit"]
            ) as ws:
                logger.info("Successfully connected to LiveKit")
                
                # Forward messages to the client
                while True:
                    try:
                        message = await ws.recv()
                        await websocket.send_text(message)
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("LiveKit connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error handling message: {str(e)}")
                        break
                    
        except Exception as e:
            logger.error(f"Error in client connection: {str(e)}", exc_info=True)
        finally:
            await websocket.close()
            logger.info(f"Closed client WebSocket connection for call {call_id}")

    def get_connection(self, call_id: str) -> Optional[dict]:
        """Get active connection information"""
        return self.active_connections.get(call_id) 