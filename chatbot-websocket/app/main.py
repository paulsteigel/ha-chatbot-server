import logging
import os
from aiohttp import web
from .stt_service import STTService
from .tts_service import TTSService
from .ai_service import AIService
from .device_manager import DeviceManager
from .ota_manager import OTAManager
from .websocket_handler import WebSocketHandler

# Setup logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
if log_level not in valid_levels:
    log_level = 'INFO'

logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def init_app():
    """Initialize application"""
    app = web.Application()
    
    # Get config from environment
    ai_provider = os.getenv('AI_PROVIDER', 'deepseek')
    ai_model = os.getenv('AI_MODEL', 'deepseek-chat')
    
    # API Keys based on provider
    if ai_provider == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    else:  # deepseek
        api_key = os.getenv('DEEPSEEK_API_KEY')
        base_url = 'https://api.deepseek.com/v1'
    
    logger.info(f"🤖 Initializing services with {ai_provider}...")
    
    # Initialize services
    stt_service = STTService(
        api_key=api_key,
        base_url=base_url
    )
    
    tts_service = TTSService(
        voice_vi=os.getenv('TTS_VOICE_VI', 'vi-VN-HoaiMyNeural'),
        voice_en=os.getenv('TTS_VOICE_EN', 'en-US-AriaNeural')
    )
    
    ai_service = AIService(
        api_key=api_key,
        base_url=base_url,
        model=ai_model,
        system_prompt=os.getenv('SYSTEM_PROMPT', 'Bạn là trợ lý AI thân thiện.'),
        max_context=int(os.getenv('MAX_CONTEXT_MESSAGES', '10')),
        temperature=float(os.getenv('TEMPERATURE', '0.7')),
        max_tokens=int(os.getenv('MAX_TOKENS', '500'))
    )
    
    device_manager = DeviceManager()
    ota_manager = OTAManager()
    
    # Initialize all services
    await stt_service.initialize()
    await tts_service.initialize()
    await ai_service.initialize()
    
    # Setup WebSocket handler
    ws_handler = WebSocketHandler(
        stt_service=stt_service,
        tts_service=tts_service,
        ai_service=ai_service,
        device_manager=device_manager,
        ota_manager=ota_manager
    )
    
    # Add routes
    app.router.add_get('/ws', ws_handler.handle)
    app.router.add_get('/health', lambda r: web.Response(text='OK'))
    app.router.add_get('/api/status', ws_handler.get_status)
    
    # Store services in app for cleanup
    app['stt_service'] = stt_service
    app['tts_service'] = tts_service
    app['ai_service'] = ai_service
    
    logger.info("✅ Application initialized")
    return app

if __name__ == '__main__':
    logger.info("🚀 Starting WebSocket server...")
    
    web.run_app(
        init_app(),
        host='0.0.0.0',
        port=5000,
        access_log=logger
    )
