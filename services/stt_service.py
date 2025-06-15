from deepgram import Deepgram
from config import Settings
import logging
import json
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class DeepgramService:
    def __init__(self, api_key: str):
        self.client = Deepgram(api_key)
        self.sample_rate = 16000
        self.channels = 1

    def _get_mime_type(self, file_extension: str) -> str:
        """Get the appropriate MIME type based on file extension"""
        mime_types = {
            'wav': 'audio/wav',
            'mp3': 'audio/mpeg',
            'm4a': 'audio/mp4'
        }
        return mime_types.get(file_extension.lower(), 'audio/wav')

    async def transcribe(self, audio_data: bytes, file_extension: str = 'wav') -> Optional[str]:
        """
        Transcribe audio data using Deepgram
        """
        try:
            if not audio_data:
                logger.warning("Empty audio data received")
                return None

            logger.debug(f"Received audio data of size: {len(audio_data)} bytes")
            logger.debug(f"File extension: {file_extension}")

            # Configure transcription options
            options = {
                "smart_format": True,
                "model": "nova-2",
                "language": "en-US",
                "punctuate": True,
                "interim_results": False
            }

            # Get appropriate MIME type
            mimetype = self._get_mime_type(file_extension)
            logger.debug(f"Using MIME type: {mimetype}")

            # Send audio data to Deepgram
            source = {
                "buffer": audio_data,
                "mimetype": mimetype
            }
            
            logger.debug("Sending audio to Deepgram...")
            response = await self.client.transcription.prerecorded(source, options)
            logger.debug(f"Deepgram response: {json.dumps(response, indent=2)}")

            # Extract transcription
            if response and "results" in response:
                if "channels" in response["results"] and response["results"]["channels"]:
                    channel = response["results"]["channels"][0]
                    if "alternatives" in channel and channel["alternatives"]:
                        transcript = channel["alternatives"][0]["transcript"]
                        if transcript and transcript.strip():
                            logger.debug(f"Transcription successful: {transcript}")
                            return transcript
                        else:
                            logger.debug("Empty transcript received")
                    else:
                        logger.warning("No alternatives found in channel")
                else:
                    logger.warning("No channels found in results")
            else:
                logger.warning("No results found in response")

            return None

        except Exception as e:
            logger.error(f"Error in transcription: {str(e)}")
            return None

    async def handle_silence(self) -> str:
        """
        Handle silence detection
        """
        return "I notice you've been quiet. Are you still there?"

    async def handle_interruption(self) -> str:
        """
        Handle interruption
        """
        return "I apologize for interrupting. Please continue."

    async def handle_unknown(self) -> str:
        """
        Handle unclear input
        """
        return "I didn't catch that. Could you please repeat?"

    async def start_stream(self) -> Dict[str, Any]:
        """
        Start a real-time streaming session with Deepgram
        """
        try:
            options = {
                "punctuate": True,
                "model": "nova-2",
                "language": "en-US",
                "smart_format": True,
                "interim_results": True
            }

            # Create a streaming connection
            connection = await self.client.transcription.live(options)
            
            logger.info("Started Deepgram streaming session")
            return {
                "connection": connection,
                "options": options
            }
        except Exception as e:
            logger.error(f"Error starting stream: {str(e)}")
            raise

    async def process_stream_chunk(self, connection: Any, audio_chunk: bytes) -> Optional[str]:
        """
        Process a chunk of audio data in a streaming session
        """
        try:
            # Send audio chunk to Deepgram
            await connection.send(audio_chunk)
            
            # Get transcription result
            result = await connection.recv()
            if result and "channel" in result:
                transcript = result["channel"]["alternatives"][0]["transcript"]
                if transcript:
                    logger.debug(f"Stream transcription: {transcript}")
                    return transcript
            
            return None
        except Exception as e:
            logger.error(f"Error processing stream chunk: {str(e)}")
            raise

    async def end_stream(self, connection: Any) -> None:
        """
        End a streaming session
        """
        try:
            await connection.finish()
            logger.info("Ended Deepgram streaming session")
        except Exception as e:
            logger.error(f"Error ending stream: {str(e)}")
            raise 