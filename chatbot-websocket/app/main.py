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


async def serve_index(request):
    """Serve the web test interface"""
    try:
        with open('/static/index.html', 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Test page not found", status=404)

async def init_app():
    """Initialize application"""
    logger.info("🚀 Starting Yên Hoà WebSocket Server...")
    logger.info("=" * 80)
    logger.info("🤖 YÊN HOÀ CHATBOT - WEBSOCKET SERVER")
    logger.info("=" * 80)
    
    # Get configuration from environment
    ai_model = os.getenv('AI_MODEL', 'deepseek-chat')
    ai_api_key = os.getenv('AI_API_KEY', '')
    ai_base_url = os.getenv('AI_BASE_URL', 'https://api.deepseek.com/v1')
    
    # System prompt for AI
    system_prompt = os.getenv('SYSTEM_PROMPT', 
        "Bạn là Yên Hoà, trợ lý AI thông minh và thân thiện của trường học. "
        "Hãy trả lời một cách ngắn gọn, rõ ràng và hữu ích."
    )
    
    # STT configuration
    stt_api_key = os.getenv('STT_API_KEY', ai_api_key)
    stt_base_url = os.getenv('STT_BASE_URL', ai_base_url)
    
    logger.info("📋 Configuration:")
    logger.info(f"   AI Model: {ai_model}")
    logger.info(f"   AI Base URL: {ai_base_url}")
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
        model=ai_model,
        api_key=ai_api_key,
        base_url=ai_base_url,
        system_prompt=system_prompt
    )
    
    logger.info("   📱 Setting up Device Manager...")
    device_manager = DeviceManager()
    
    logger.info("   🔄 Setting up OTA Manager...")
    ota_manager = OTAManager()
    
    # Start services (only if they have start() method)
    logger.info("🚀 Starting services...")
    
    # Check and start services
    if hasattr(stt_service, 'start'):
        await stt_service.start()
    else:
        logger.info("✅ STT Service ready (no start() needed)")
    
    if hasattr(tts_service, 'start'):
        await tts_service.start()
    else:
        logger.info("✅ TTS Service ready (no start() needed)")
    
    if hasattr(ai_service, 'start'):
        await ai_service.start()
    else:
        logger.info("✅ AI Service ready (no start() needed)")
    
    # Test TTS
    logger.info("🧪 Testing TTS service...")
    if hasattr(tts_service, 'test'):
        await tts_service.test()
    else:
        logger.info("⚠️ TTS test() method not available")
    
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
    app.router.add_get('/', serve_index)
    app.router.add_static('/static', '/static')
    
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
