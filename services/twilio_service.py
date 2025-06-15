from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from config import get_settings, update_app_host
import logging
from typing import Optional, Dict
import uuid
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str, app_host: str):
        self.client = Client(account_sid, auth_token, region='us1')
        self.phone_number = phone_number
        self.app_host = app_host
        self.active_calls: Dict[str, dict] = {}
        # Update the global settings with the provided app_host
        update_app_host(app_host)

    def update_app_host(self, new_host: str):
        """Update the app host and settings"""
        self.app_host = new_host
        update_app_host(new_host)
        logger.info(f"Updated APP_HOST to: {new_host}")

    async def initiate_call(self, phone_number: str, amount: float, due_date: str, account_number: Optional[str] = None) -> dict:
        """Initiate a new call"""
        try:
            logger.info(f"Starting call to {phone_number}")
            
            # Validate phone number format
            if not phone_number.startswith('+'):
                raise HTTPException(status_code=400, detail="Phone number must start with country code (e.g., +91)")

            # Generate a unique call ID
            call_id = str(uuid.uuid4())
            logger.info(f"Generated call ID: {call_id}")
            
            # Construct webhook URLs
            twiml_url = f"https://{self.app_host}/twiml/{call_id}"
            status_callback_url = f"https://{self.app_host}/webhook/twilio"
            
            logger.info(f"Using TwiML URL: {twiml_url}")
            logger.info(f"Using Status Callback URL: {status_callback_url}")
            
            # Make the outbound call
            call = self.client.calls.create(
                to=phone_number,
                from_=self.phone_number,
                url=twiml_url,
                status_callback=status_callback_url,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            logger.info(f"Twilio call created with SID: {call.sid}")
            
            # Store call information
            self.active_calls[call_id] = {
                "twilio_sid": call.sid,
                "phone_number": phone_number,
                "amount": amount,
                "due_date": due_date,
                "account_number": account_number
            }
            
            return {
                "call_id": call_id,
                "status": "initiated",
                "twilio_sid": call.sid
            }
            
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create call: {str(e)}")

    def generate_twiml(self, call_id: str) -> str:
        """Generate TwiML for the call"""
        try:
            logger.info(f"Generating TwiML for call {call_id}")
            response = VoiceResponse()
            
            # Create a Connect verb with Stream
            connect = Connect()
            stream_url = f"wss://{self.app_host}/stream/{call_id}"
            logger.info(f"Using WebSocket URL: {stream_url}")
            connect.stream(url=stream_url)
            response.append(connect)
            
            # Add a fallback message
            response.say("Connecting to the AI agent. Please wait.", voice="Polly.Amy")
            
            logger.info(f"Generated TwiML: {str(response)}")
            return str(response)
        except Exception as e:
            logger.error(f"Error generating TwiML: {str(e)}")
            response = VoiceResponse()
            response.say("We're experiencing technical difficulties. Please try again later.", voice="Polly.Amy")
            return str(response)

    def get_call_info(self, call_id: str) -> Optional[dict]:
        """Get information about an active call"""
        return self.active_calls.get(call_id)

    def end_call(self, call_id: str):
        """End a call and clean up resources"""
        try:
            if call_id in self.active_calls:
                call_info = self.active_calls[call_id]
                twilio_sid = call_info["twilio_sid"]
                
                # End the call in Twilio
                self.client.calls(twilio_sid).update(status="completed")
                
                # Remove from active calls
                del self.active_calls[call_id]
                
                logger.info(f"Call {call_id} ended and resources cleaned up")
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {str(e)}")

    async def get_call_status(self, call_sid: str) -> str:
        """Get the current status of a call"""
        try:
            call = self.client.calls(call_sid).fetch()
            return call.status
        except Exception as e:
            logger.error(f"Error getting call status: {str(e)}")
            raise 