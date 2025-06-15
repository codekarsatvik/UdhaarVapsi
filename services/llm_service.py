from groq import Groq
import logging
from typing import List, Dict, Any
import json
from config import get_settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str, model: str = None):
        self.client = Groq(api_key=api_key)
        settings = get_settings()
        self.model = model or settings.GROQ_MODEL
        logger.info(f"Initializing LLM service with model: {self.model}")
        self.conversation_history: Dict[str, List[Dict[str, str]]] = {}

    async def generate_response(self, user_input: str, call_id: str) -> str:
        """
        Generate a response using Groq's LLM model based on user input and conversation history
        """
        try:
            # Initialize conversation history for new calls
            if call_id not in self.conversation_history:
                self.conversation_history[call_id] = [
                    {
                        "role": "system",
                        "content": """You are a professional debt collection agent. Follow these rules:
                        1. Keep responses short and clear - maximum 2-3 sentences
                        2. Use simple, conversational language
                        3. Avoid special characters, emojis, or formatting
                        4. Focus on one topic at a time
                        5. Be polite and professional
                        6. Use numbers instead of words for amounts
                        7. Avoid abbreviations
                        8. Use natural pauses and rhythm in speech
                        9. Show empathy while maintaining professionalism
                        10. Use active voice for clarity
                        
                        Example responses:
                        - "I understand this might be a difficult situation. Would you like to discuss a payment plan that works for you?"
                        - "The outstanding amount is 5000 rupees. When would be a good time for you to make the payment?"
                        - "I can help you set up a payment plan. What amount would you be comfortable paying each month?"
                        """
                    }
                ]

            # Add user input to conversation history
            self.conversation_history[call_id].append({
                "role": "user",
                "content": user_input
            })

            # Generate response using Groq
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history[call_id],
                temperature=0.7,
                max_tokens=150,  # Increased for more natural responses
                top_p=0.95,
                presence_penalty=0.6,  # Encourage diverse responses
                frequency_penalty=0.3,  # Reduce repetition
                stream=False
            )

            # Extract and store response
            bot_response = response.choices[0].message.content.strip()
            
            # Clean up response
            bot_response = bot_response.replace('"', '')  # Remove quotes
            bot_response = bot_response.replace('"', '')  # Remove smart quotes
            bot_response = bot_response.replace('"', '')  # Remove other quote types
            bot_response = bot_response.replace('"', '')
            bot_response = bot_response.replace('...', '.')  # Replace ellipsis with period
            bot_response = bot_response.replace('…', '.')  # Replace other ellipsis
            bot_response = bot_response.replace('–', '-')  # Replace en dash
            bot_response = bot_response.replace('—', '-')  # Replace em dash
            
            # Remove any remaining special characters
            bot_response = ''.join(char for char in bot_response if char.isprintable() and ord(char) < 128)
            
            self.conversation_history[call_id].append({
                "role": "assistant",
                "content": bot_response
            })

            # Keep conversation history manageable
            if len(self.conversation_history[call_id]) > 10:
                self.conversation_history[call_id] = self.conversation_history[call_id][-10:]

            logger.debug(f"Generated response: {bot_response}")
            return bot_response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    async def handle_silence(self, call_id: str) -> str:
        """
        Generate a response for silence detection
        """
        return await self.generate_response(
            "The customer has been silent for a while. Please check if they're still there.",
            call_id
        )

    async def handle_interruption(self, call_id: str) -> str:
        """
        Generate a response for interruption
        """
        return await self.generate_response(
            "The customer interrupted. Please acknowledge and continue the conversation.",
            call_id
        )

    async def handle_unknown(self, call_id: str) -> str:
        """
        Generate a response for unclear input
        """
        return await self.generate_response(
            "The customer's response was unclear. Please ask them to repeat or clarify.",
            call_id
        )

    def clear_conversation(self, call_id: str) -> None:
        """
        Clear conversation history for a call
        """
        if call_id in self.conversation_history:
            del self.conversation_history[call_id]
            logger.info(f"Cleared conversation history for call: {call_id}") 