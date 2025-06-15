from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from config import Settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.client = Client(account_sid, auth_token, region='us1')
        self.phone_number = phone_number

    async def make_call(self, to_number: str, room_name: str) -> str:
        """
        Initiate an outbound call using Twilio
        """
        try:
            # Create TwiML for the call
            response = VoiceResponse()
            connect = Connect()
            connect.stream(url=f"wss://{self.settings.app_host}/stream/{room_name}")
            response.append(connect)
            
            # Add a fallback message
            response.say("Connecting to the AI agent. Please wait.")

            # Make the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                twiml=str(response),
                status_callback=f"https://8dcf-2409-40d0-1c-503f-4415-7b7a-6aec-63de.ngrok-free.app/webhook/twilio/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            
            logger.info(f"Initiated call to {to_number} with SID: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Error making call: {str(e)}")
            raise

    async def end_call(self, call_sid: str) -> None:
        """
        End an active call
        """
        try:
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Ended call with SID: {call_sid}")
        except Exception as e:
            logger.error(f"Error ending call: {str(e)}")
            raise

    async def get_call_status(self, call_sid: str) -> str:
        """
        Get the current status of a call
        """
        try:
            call = self.client.calls(call_sid).fetch()
            return call.status
        except Exception as e:
            logger.error(f"Error getting call status: {str(e)}")
            raise

    def generate_twiml(self, room_name: str) -> str:
        """Generate TwiML for the call."""
        try:
            response = VoiceResponse()
            connect = Connect()
            connect.stream(url=f"wss://8dcf-2409-40d0-1c-503f-4415-7b7a-6aec-63de.ngrok-free.app/stream/{room_name}")
            response.append(connect)
            
            # Add a fallback message
            response.say("Connecting to the AI agent. Please wait.")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error generating TwiML: {str(e)}")
            response = VoiceResponse()
            response.say("We're experiencing technical difficulties. Please try again later.")
            return str(response) 