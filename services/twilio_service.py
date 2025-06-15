from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from config import get_settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.client = Client(account_sid, auth_token)
        self.phone_number = phone_number
        self.settings = get_settings()

    async def make_call(self, to_number: str, room_name: str) -> str:
        """
        Initiate an outbound call using Twilio
        """
        try:
            # Create TwiML for the call
            response = VoiceResponse()
            connect = Connect()
            
            # Add status callback
            connect.stream(
                url=f"wss://{self.settings.APP_HOST}/stream/{room_name}",
                status_callback=f"https://{self.settings.APP_HOST}/webhook/twilio/status"
            )
            response.append(connect)
            
            # Add a fallback message
            response.say("Connecting to the AI agent. Please wait.")

            # Make the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                twiml=str(response),
                status_callback=f"https://{self.settings.APP_HOST}/webhook/twilio/status",
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
            connect.stream(url=f"wss://{self.settings.APP_HOST}/stream/{room_name}")
            response.append(connect)
            
            # Add a fallback message
            response.say("Connecting to the AI agent. Please wait.")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error generating TwiML: {str(e)}")
            response = VoiceResponse()
            response.say("We're experiencing technical difficulties. Please try again later.")
            return str(response)

    async def handle_incoming_call(self, room_name: str):
        try:
            # Generate TwiML for incoming call
            response = VoiceResponse()
            connect = Connect()
            connect.stream(url=f"wss://{self.settings.APP_HOST}/stream/{room_name}")
            response.append(connect)
            
            return str(response)
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            raise 