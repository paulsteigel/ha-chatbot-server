import os
import logging
from aiohttp import web
from .websocket_handler import WebSocketHandler
from .stt_service import STTService
from .tts_service import TTSService
from .ai_service import AIService
from .device_manager import DeviceManager
from .ota_manager import OTAManager

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def init_app():
    """Initialize application"""
    app = web.Application()
    
    # Get config
    ai_api_key = os.getenv('AI_API_KEY')
    ai_base_url = os.getenv('AI_BASE_URL')
    
    if not ai_api_key:
        logger.error("❌ AI_API_KEY not configured!")
        raise ValueError("AI_API_KEY required")
    
    # Initialize services
    stt_service = STTService(
        api_key=ai_api_key,
        base_url=ai_base_url
    )
    
    tts_service = TTSService(
        voice_vi=os.getenv('TTS_VOICE_VI', 'vi-VN-HoaiMyNeural'),
        voice_en=os.getenv('TTS_VOICE_EN', 'en-US-AriaNeural')
    )
    
    ai_service = AIService(
        api_key=ai_api_key,
        model=os.getenv('AI_MODEL', 'gpt-4o-mini'),
        base_url=ai_base_url,
        system_prompt=os.getenv('CUSTOM_PROMPT', 'Bạn là trợ lý thân thiện.')
    )
    
    device_manager = DeviceManager()
    ota_manager = OTAManager(firmware_dir='/data/firmware')
    
    # Initialize
    await stt_service.initialize()
    await tts_service.initialize()
    await ai_service.initialize()
    
    # Store in app
    app['stt'] = stt_service
    app['tts'] = tts_service
    app['ai'] = ai_service
    app['devices'] = device_manager
    app['ota'] = ota_manager
    
    # WebSocket handler
    ws_handler = WebSocketHandler(app)
    
    # Routes
    app.router.add_get('/ws', ws_handler.websocket_handler)
    app.router.add_get('/health', lambda r: web.Response(text='OK'))
    app.router.add_get('/', lambda r: web.FileResponse('./app/static/index.html'))
    
    logger.info("✅ Application initialized")
    return app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Starting server on port {port}")
    
    web.run_app(
        init_app(),
        host='0.0.0.0',
        port=port
    )
