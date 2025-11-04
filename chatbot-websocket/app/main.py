"""
Main application entry point
"""
import logging
import os
import asyncio
from aiohttp import web

from app.device_manager import DeviceManager
from app.ai_service import AIService
from app.tts_service import TTSService
from app.stt_service import STTService
from app.ota_manager import OTAManager
from app.websocket_handler import WebSocketHandler


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def health_handler(request):
    """Health check endpoint"""
    return web.Response(text='OK')


async def status_handler(request):
    """Status endpoint"""
    device_manager = request.app['device_manager']
    
    status = {
        'status': 'ok',
        'devices': device_manager.get_device_count(),
        'version': '1.0.0'
    }
    
    return web.json_response(status)


async def init_app():
    """Initialize application"""
    logger.info("🚀 Starting Yên Hoà WebSocket Server...")
    logger.info("=" * 80)
    logger.info("🤖 YÊN HOÀ CHATBOT - WEBSOCKET SERVER")
    logger.info("=" * 80)
    
    # Get configuration from environment
    ai_provider = os.getenv('AI_PROVIDER', 'deepseek')
    ai_model = os.getenv('AI_MODEL', 'deepseek-chat')
    ai_api_key = os.getenv('AI_API_KEY', '')
    
    # STT configuration
    stt_api_key = os.getenv('STT_API_KEY', ai_api_key)  # Use AI key as fallback
    stt_base_url = os.getenv('STT_BASE_URL', 'https://api.deepseek.com/v1')
    
    logger.info("📋 Configuration:")
    logger.info(f"   AI Provider: {ai_provider}")
    logger.info(f"   AI Model: {ai_model}")
    logger.info(f"   TTS: Google TTS (gTTS) 🆓 FREE")
    logger.info(f"   STT: {'Enabled' if stt_api_key else 'Disabled (no API key)'}")
    logger.info(f"   Log Level: INFO")
    logger.info("=" * 80)
    
    # Initialize services
    logger.info("🔧 Initializing services...")
    
    logger.info("   📝 Setting up Speech-to-Text...")
    stt_service = STTService(
        api_key=stt_api_key,
        base_url=stt_base_url
    )
    
    logger.info("   🔊 Setting up Text-to-Speech (Google TTS)...")
    tts_service = TTSService()
    
    logger.info("   🤖 Setting up AI Service...")
    ai_service = AIService(
        provider=ai_provider,
        model=ai_model
    )
    
    logger.info("   📱 Setting up Device Manager...")
    device_manager = DeviceManager()
    
    logger.info("   🔄 Setting up OTA Manager...")
    ota_manager = OTAManager()
    
    # Start services
    logger.info("🚀 Starting services...")
    await stt_service.start()
    await tts_service.start()
    await ai_service.start()
    
    # Test TTS
    logger.info("🧪 Testing TTS service...")
    await tts_service.test()
    
    # Setup WebSocket handler
    logger.info("🔌 Setting up WebSocket handler...")
    ws_handler = WebSocketHandler(
        device_manager=device_manager,
        ai_service=ai_service,
        tts_service=tts_service,
        stt_service=stt_service
    )
    
    # Create application
    app = web.Application()
    
    # Store services in app
    app['device_manager'] = device_manager
    app['ai_service'] = ai_service
    app['tts_service'] = tts_service
    app['stt_service'] = stt_service
    app['ota_manager'] = ota_manager
    app['ws_handler'] = ws_handler
    
    # Setup routes
    app.router.add_get('/ws', ws_handler.handle)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/api/status', status_handler)
    
    logger.info("=" * 80)
    logger.info("✅ Application initialized successfully!")
    logger.info("=" * 80)
    logger.info("📡 Server endpoints:")
    logger.info("   WebSocket: ws://0.0.0.0:5000/ws")
    logger.info("   Health: http://0.0.0.0:5000/health")
    logger.info("   Status: http://0.0.0.0:5000/api/status")
    logger.info("=" * 80)
    
    return app


if __name__ == '__main__':
    try:
        logger.info("🔧 Initializing...")
        
        # Run application
        web.run_app(
            init_app(),
            host='0.0.0.0',
            port=5000,
            access_log=logger
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise
