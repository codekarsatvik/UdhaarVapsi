import logging
import uuid
from typing import Dict, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CallService:
    def __init__(self, twilio_service, livekit_service):
        self.twilio_service = twilio_service
        self.livekit_service = livekit_service

    async def initiate_call(self, phone_number: str, amount: float, due_date: str, account_number: Optional[str] = None) -> dict:
        """Initiate a new call"""
        try:
            # Create LiveKit room first
            call_id = str(uuid.uuid4())
            room_name = f"call-{call_id}"
            await self.livekit_service.create_room(room_name)
            logger.info(f"LiveKit room created: {room_name}")
            
            # Initiate call through Twilio service
            call_info = await self.twilio_service.initiate_call(
                phone_number=phone_number,
                amount=amount,
                due_date=due_date,
                account_number=account_number
            )
            
            # Add LiveKit room info to response
            call_info["livekit_room"] = room_name
            return call_info
            
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            try:
                await self.livekit_service.cleanup_room(room_name)
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to create call: {str(e)}")

    def generate_twiml(self, call_id: str) -> str:
        """Generate TwiML for the call"""
        return self.twilio_service.generate_twiml(call_id)

    async def end_call(self, call_id: str):
        """End a call and clean up resources"""
        try:
            # Get call info
            call_info = self.twilio_service.get_call_info(call_id)
            if call_info:
                room_name = f"call-{call_id}"
                
                # Clean up LiveKit room
                await self.livekit_service.cleanup_room(room_name)
                
                # End Twilio call
                self.twilio_service.end_call(call_id)
                
                logger.info(f"Call {call_id} ended and resources cleaned up")
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {str(e)}")

    def get_call_info(self, call_id: str) -> Optional[dict]:
        """Get information about an active call"""
        return self.twilio_service.get_call_info(call_id) 