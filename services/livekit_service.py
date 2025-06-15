from livekit import rtc
from livekit.rtc import room as lk_room
from config import Settings
import logging
import asyncio
from typing import Optional
import jwt
import time
import aiohttp
from config import get_settings
import numpy as np

logger = logging.getLogger(__name__)

class LiveKitService:
    def __init__(self, api_key: str, api_secret: str, url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.url = url
        self.rooms: dict[str, lk_room.Room] = {}
        self.audio_tracks = {}

    def _generate_token(self, room_name: str, participant_name: str = "agent") -> str:
        """
        Generate a LiveKit token for room access
        """
        try:
            now = int(time.time())
            exp = now + 3600  # Token expires in 1 hour

            claims = {
                "iss": self.api_key,
                "sub": participant_name,
                "exp": exp,
                "nbf": now,
                "room": room_name,
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
            if isinstance(self.api_secret, str):
                secret = self.api_secret.encode('utf-8')
            else:
                secret = self.api_secret

            token = jwt.encode(claims, secret, algorithm="HS256")
            logger.debug(f"Generated token for room {room_name} with claims: {claims}")
            return token
        except Exception as e:
            logger.error(f"Error generating token: {str(e)}")
            raise

    async def create_room(self, room_name: str):
        """Create a LiveKit room"""
        try:
            logger.info(f"Creating LiveKit room: {room_name}")
            
            # Use the LiveKit URL as provided
            base_url = self.url
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            
            # Create room using LiveKit API
            async with aiohttp.ClientSession() as session:
                # Generate admin token for API access
                admin_token = self._generate_token(room_name, "admin")
                
                async with session.post(
                    f"{base_url}/twirp/livekit.RoomService/CreateRoom",
                    headers={
                        "Authorization": f"Bearer {admin_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": room_name,
                        "empty_timeout": 300,
                        "max_participants": 2
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to create room: {error_text}")
                        raise Exception(f"Failed to create room: {error_text}")
                    
                    result = await response.json()
                    logger.info(f"Created LiveKit room: {result}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error creating LiveKit room: {str(e)}")
            raise

    async def send_audio(self, audio_data: bytes, room_name: str) -> None:
        """
        Send audio data to the LiveKit room
        """
        try:
            room = self.rooms.get(room_name)
            if not room:
                raise ValueError(f"Room {room_name} not found")

            # Create or get existing audio track
            if room_name not in self.audio_tracks:
                # Create audio track with specific parameters
                track = rtc.LocalAudioTrack.create(
                    name="agent_audio",
                    source=rtc.AudioSource.MICROPHONE,
                    options={
                        "sampleRate": 48000,
                        "channels": 1,
                        "bitsPerSample": 16
                    }
                )
                self.audio_tracks[room_name] = track
                await room.local_participant.publish_track(track)
                logger.debug(f"Created and published audio track for room: {room_name}")

            # Ensure audio data is in the correct format
            if not isinstance(audio_data, bytes):
                raise ValueError(f"Audio data must be in bytes format, got {type(audio_data)}")

            # Log audio data details
            logger.debug(f"Audio data length: {len(audio_data)} bytes")
            
            # Send audio data
            track = self.audio_tracks[room_name]
            try:
                # Convert bytes to numpy array for validation
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                logger.debug(f"Audio array shape: {audio_array.shape}, dtype: {audio_array.dtype}")
                
                # Ensure the audio data is in the correct format
                if audio_array.dtype != np.int16:
                    audio_array = audio_array.astype(np.int16)
                    audio_data = audio_array.tobytes()
                
                await track.write(audio_data)
                logger.debug(f"Successfully sent audio data to room: {room_name}")
            except Exception as write_error:
                logger.error(f"Error writing to audio track: {str(write_error)}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Error sending audio: {str(e)}", exc_info=True)
            raise

    async def cleanup_room(self, room_name: str):
        """Clean up a LiveKit room"""
        try:
            logger.info(f"Cleaning up LiveKit room: {room_name}")
            
            # Use the LiveKit URL as provided
            base_url = self.url
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            
            # Generate admin token for API access
            admin_token = self._generate_token(room_name, "admin")
            
            # Delete room using LiveKit API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/twirp/livekit.RoomService/DeleteRoom",
                    headers={
                        "Authorization": f"Bearer {admin_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "room": room_name
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to delete room: {error_text}")
                        raise Exception(f"Failed to delete room: {error_text}")
                    
                    logger.info(f"Cleaned up LiveKit room: {room_name}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up LiveKit room: {str(e)}")
            raise

    async def get_room_participants(self, room_name: str) -> list[str]:
        """
        Get list of participants in a room
        """
        try:
            room = self.rooms.get(room_name)
            if not room:
                return []
            
            return [p.identity for p in room.participants.values()]
        except Exception as e:
            logger.error(f"Error getting room participants: {str(e)}")
            raise 