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
async def init_app():
    """Initialize application"""
    app = web.Application()
    
    # Get config from environment
    openai_api_key = os.getenv('OPENAI_API_KEY')
    openai_base_url = os.getenv('OPENAI_BASE_URL')
    ai_model = os.getenv('AI_MODEL', 'gpt-4o-mini')
    
    logger.info("🚀 Initializing services...")
    
    # ⭐ Add health check FIRST (before slow initialization)
    async def health_check(request):
        return web.Response(text='OK', status=200)
    
    app.router.add_get('/health', health_check)
    
    # Now initialize slow services
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
    
    # Initialize services in background
    async def init_services():
        await stt_service.initialize()
        await tts_service.initialize()
        await ai_service.initialize()
        logger.info("✅ All services initialized")
    
    # Setup WebSocket handler
    ws_handler = WebSocketHandler(
        stt_service=stt_service,
        tts_service=tts_service,
        ai_service=ai_service,
        device_manager=device_manager,
        ota_manager=ota_manager
    )
    
    app.router.add_get('/ws', ws_handler.handle)
    
    # Store services
    app['stt_service'] = stt_service
    app['tts_service'] = tts_service
    app['ai_service'] = ai_service
    
    # Start service initialization in background
    app.on_startup.append(lambda app: init_services())
    
    logger.info("✅ Application routes configured")
    return app
