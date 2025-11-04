"""
WebSocket Server for Yên Hoà Chatbot
Home Assistant Add-on Version with FREE Google TTS
"""
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
    
    logger.info("=" * 80)
    logger.info("🤖 YÊN HOÀ CHATBOT - WEBSOCKET SERVER")
    logger.info("=" * 80)
    logger.info(f"📋 Configuration:")
    logger.info(f"   AI Provider: {ai_provider}")
    logger.info(f"   AI Model: {ai_model}")
    logger.info(f"   TTS: Google TTS (gTTS) 🆓 FREE")
    logger.info(f"   Log Level: {log_level}")
    logger.info("=" * 80)
    
    # Initialize services
    logger.info("🔧 Initializing services...")
    
    # STT Service
    logger.info("   📝 Setting up Speech-to-Text...")
    stt_service = STTService(
        api_key=api_key,
        base_url=base_url
    )
    
    # TTS Service (FREE Google TTS)
    logger.info("   🔊 Setting up Text-to-Speech (Google TTS)...")
    tts_service = TTSService(
        voice_vi='vi',  # Vietnamese
        voice_en='en'   # English
    )
    
    # AI Service
    logger.info("   🤖 Setting up AI Service...")
    ai_service = AIService(
        api_key=api_key,
        base_url=base_url,
        model=ai_model,
        system_prompt=os.getenv('SYSTEM_PROMPT', 
            'Bạn là Yên Hoà, trợ lý AI thân thiện của trường học. '
            'Bạn giúp học sinh và giáo viên với các câu hỏi về học tập và đời sống.'),
        max_context=int(os.getenv('MAX_CONTEXT_MESSAGES', '10')),
        temperature=float(os.getenv('TEMPERATURE', '0.7')),
        max_tokens=int(os.getenv('MAX_TOKENS', '500'))
    )
    
    # Device Manager
    logger.info("   📱 Setting up Device Manager...")
    device_manager = DeviceManager()
    
    # OTA Manager
    logger.info("   🔄 Setting up OTA Manager...")
    ota_manager = OTAManager()
    
    # Initialize all services
    logger.info("🚀 Starting services...")
    await stt_service.initialize()
    await tts_service.initialize()
    await ai_service.initialize()
    
    # Test TTS (important!)
    logger.info("🧪 Testing TTS service...")
    await tts_service.test()
    
    # Setup WebSocket handler
    logger.info("🔌 Setting up WebSocket handler...")
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
    
    logger.info("=" * 80)
    logger.info("✅ Application initialized successfully!")
    logger.info("=" * 80)
    logger.info("📡 Server endpoints:")
    logger.info("   WebSocket: ws://0.0.0.0:5000/ws")
    logger.info("   Health: http://0.0.0.0:5000/health")
    logger.info("   Status: http://0.0.0.0:5000/api/status")
    logger.info("=" * 80)
    
    return app

async def cleanup(app):
    """Cleanup resources"""
    logger.info("🧹 Cleaning up resources...")
    # Add cleanup code if needed

if __name__ == '__main__':
    logger.info("🚀 Starting Yên Hoà WebSocket Server...")
    
    app = init_app()
    
    web.run_app(
        app,
        host='0.0.0.0',
        port=5000,
        access_log=logger
    )
