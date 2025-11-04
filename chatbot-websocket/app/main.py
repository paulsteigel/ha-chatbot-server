import logging
import os
from aiohttp import web
from .stt_service import STTService
from .tts_service import TTSService
from .ai_service import AIService
from .device_manager import DeviceManager
from .ota_manager import OTAManager
from .websocket_handler import WebSocketHandler

# ✅ FIX: Handle invalid log level
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

# Validate log level
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
    openai_api_key = os.getenv('OPENAI_API_KEY')
    openai_base_url = os.getenv('OPENAI_BASE_URL')
    ai_model = os.getenv('AI_MODEL', 'gpt-4o-mini')
    
    logger.info("🚀 Initializing services...")
    
    # Initialize services
    stt_service = STTService(
        api_key=openai_api_key,
        base_url=openai_base_url
    )
    
    tts_service = TTSService(
        voice_vi=os.getenv('TTS_VOICE_VI', 'vi-VN-HoaiMyNeural'),
        voice_en=os.getenv('TTS_VOICE_EN', 'en-US-AriaNeural')
    )
    
    ai_service = AIService(
        api_key=openai_api_key,
        base_url=openai_base_url,
        model=ai_model
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
    
    # Store services in app for cleanup
    app['stt_service'] = stt_service
    app['tts_service'] = tts_service
    app['ai_service'] = ai_service
    
    logger.info("✅ Application initialized")
    return app

if __name__ == '__main__':
    logger.info("🎯 Starting WebSocket server...")
    
    web.run_app(
        init_app(),
        host='0.0.0.0',
        port=5000,
        access_log=logger,
        print=lambda msg: logger.info(f"🌐 {msg}")
    )
