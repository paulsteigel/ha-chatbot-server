import os
import logging
import uvicorn
from fastapi import FastAPI
from app.websocket_handler import websocket_endpoint
from app.ai_service import AIService
from app.stt_service import STTService
from app.tts_service import TTSService

# Setup logging from environment
log_level = os.getenv('LOG_LEVEL', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Build config from environment variables
config = {
    'ai_provider': os.getenv('AI_PROVIDER', 'deepseek'),
    'ai_model': os.getenv('AI_MODEL', 'deepseek-chat'),
    'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
    'openai_base_url': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
    'deepseek_api_key': os.getenv('DEEPSEEK_API_KEY', ''),
    'tts_voice_vi': os.getenv('TTS_VOICE_VI', 'vi-VN-HoaiMyNeural'),
    'tts_voice_en': os.getenv('TTS_VOICE_EN', 'en-US-AriaNeural'),
    'system_prompt': os.getenv('SYSTEM_PROMPT', 'Bạn là trợ lý AI thân thiện.'),
    'max_context_messages': int(os.getenv('MAX_CONTEXT_MESSAGES', '10')),
    'temperature': float(os.getenv('TEMPERATURE', '0.7')),
    'max_tokens': int(os.getenv('MAX_TOKENS', '500'))
}

logger.info("="*60)
logger.info("ESP32 Chatbot WebSocket Server Starting...")
logger.info(f"AI Provider: {config['ai_provider']}")
logger.info(f"AI Model: {config['ai_model']}")
logger.info(f"Log Level: {log_level}")
logger.info("="*60)

# Initialize services
ai_service = AIService(config)
stt_service = STTService(config)
tts_service = TTSService(config)

# Create FastAPI app
app = FastAPI(title="ESP32 Chatbot WebSocket Server")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker"""
    return {
        "status": "healthy",
        "provider": config['ai_provider'],
        "model": config['ai_model']
    }

# Register WebSocket endpoint
app.add_websocket_route("/ws", websocket_endpoint)

if __name__ == "__main__":
    port = int(os.getenv('PORT', '5000'))
    logger.info(f"🚀 Starting server on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=log_level.lower()
    )
