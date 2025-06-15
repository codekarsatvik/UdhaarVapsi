# AI Debt Collection Voice Agent

An intelligent voice agent that makes outbound calls to remind users about unpaid bills using natural conversation.

## Features

- 📞 Outbound calling using Twilio
- 🔁 Real-time audio streaming with LiveKit
- 🗣️ Speech-to-Text using Deepgram
- 🧠 Conversational AI using OpenAI GPT-4
- 🔊 Natural Text-to-Speech using ElevenLabs

## Prerequisites

- Python 3.9+
- Twilio Account (with a US phone number)
- Deepgram API Key
- OpenAI API Key
- ElevenLabs API Key
- LiveKit Server

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_number
   DEEPGRAM_API_KEY=your_deepgram_key
   OPENAI_API_KEY=your_openai_key
   ELEVENLABS_API_KEY=your_elevenlabs_key
   LIVEKIT_API_KEY=your_livekit_key
   LIVEKIT_API_SECRET=your_livekit_secret
   LIVEKIT_URL=your_livekit_url
   ```

## Running the Application

1. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

2. The server will start on `http://localhost:8000`

## Project Structure

- `main.py` - FastAPI application entry point
- `config.py` - Configuration and environment variables
- `services/`
  - `twilio_service.py` - Twilio call handling
  - `livekit_service.py` - LiveKit audio streaming
  - `stt_service.py` - Speech-to-Text with Deepgram
  - `llm_service.py` - LLM conversation handling
  - `tts_service.py` - Text-to-Speech with ElevenLabs
- `models/` - Data models and schemas
- `utils/` - Utility functions

## API Endpoints

- `POST /call` - Initiate an outbound call
- `POST /webhook/twilio` - Twilio webhook handler
- `POST /webhook/livekit` - LiveKit webhook handler

## License

MIT 