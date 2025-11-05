"""
School Chatbot WebSocket Server
Main FastAPI application with WebSocket support for ESP32 devices
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

# Import services
from app.ai_service import AIService
from app.tts_service import TTSService
from app.stt_service import STTService
from app.device_manager import DeviceManager
from app.ota_manager import OTAManager
from app.websocket_handler import WebSocketHandler


# ==============================================================================
# Configuration
# ==============================================================================

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Main')

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))

# AI configuration
AI_PROVIDER = os.getenv('AI_PROVIDER', 'openai')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4o-mini')

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')


# ==============================================================================
# Service Instances (Global)
# ==============================================================================

ai_service = None
tts_service = None
stt_service = None
device_manager = None
ota_manager = None
ws_handler = None


# ==============================================================================
# Lifespan Context Manager
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI
    Handles startup and shutdown events
    """
    # STARTUP
    logger.info("=" * 80)
    logger.info("🚀 SCHOOL CHATBOT WEBSOCKET SERVER")
    logger.info("=" * 80)
    
    global ai_service, tts_service, stt_service, device_manager, ota_manager, ws_handler
    
    try:
        # Initialize Device Manager
        logger.info("📱 Initializing Device Manager...")
        device_manager = DeviceManager()
        
        # Initialize OTA Manager
        logger.info("📦 Initializing OTA Manager...")
        ota_manager = OTAManager(firmware_version="1.0.0")
        
        # Initialize AI Service
        logger.info(f"🤖 Initializing AI Service ({AI_PROVIDER})...")
        ai_service = AIService(provider=AI_PROVIDER, model=AI_MODEL)
        await ai_service.initialize()
        
        # Initialize TTS Service
        logger.info("🔊 Initializing TTS Service...")
        if AI_PROVIDER == 'openai':
            tts_service = TTSService(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        else:
            # For DeepSeek, we still use OpenAI for TTS (if available)
            if OPENAI_API_KEY:
                tts_service = TTSService()
            else:
                logger.warning("⚠️ No OpenAI key for TTS, using DeepSeek key (may not work)")
                tts_service = TTSService(api_key=DEEPSEEK_API_KEY, base_url=OPENAI_BASE_URL)
        
        await tts_service.initialize()
        
        # Initialize STT Service
        logger.info("🎤 Initializing STT Service...")
        if AI_PROVIDER == 'openai':
            stt_service = STTService()
        else:
            # For DeepSeek, we still use OpenAI for STT (if available)
            if OPENAI_API_KEY:
                stt_service = STTService()
            else:
                logger.warning("⚠️ No OpenAI key for STT, using DeepSeek key (may not work)")
                stt_service = STTService(api_key=DEEPSEEK_API_KEY, base_url=OPENAI_BASE_URL)
        
        await stt_service.initialize()
        
        # Initialize WebSocket Handler
        logger.info("🔌 Initializing WebSocket Handler...")
        ws_handler = WebSocketHandler(
            ai_service=ai_service,
            tts_service=tts_service,
            stt_service=stt_service,
            device_manager=device_manager,
            ota_manager=ota_manager
        )
        
        logger.info("=" * 80)
        logger.info("✅ ALL SERVICES INITIALIZED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"🌐 Server listening on: {HOST}:{PORT}")
        logger.info(f"📡 WebSocket endpoint: ws://{HOST}:{PORT}/ws")
        logger.info(f"🌍 Web interface: http://{HOST}:{PORT}/")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ STARTUP FAILED: {e}", exc_info=True)
        raise
    
    yield  # Server is running
    
    # SHUTDOWN
    logger.info("=" * 80)
    logger.info("🛑 SHUTTING DOWN SERVER...")
    logger.info("=" * 80)
    
    # Cleanup resources
    if device_manager:
        active_devices = device_manager.get_device_count()
        logger.info(f"📊 Active devices at shutdown: {active_devices}")
    
    logger.info("✅ Server shutdown complete")
    logger.info("=" * 80)


# ==============================================================================
# FastAPI Application
# ==============================================================================

app = FastAPI(
    title="School Chatbot WebSocket Server",
    description="WebSocket server for ESP32-based school chatbot",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
if os.path.exists('/app/static'):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
    logger.info("📁 Static files mounted at /static")


# ==============================================================================
# HTTP Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface"""
    index_path = "/app/static/index.html"
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>School Chatbot Server</title></head>
                <body style="font-family: Arial; padding: 50px; text-align: center;">
                    <h1>🤖 School Chatbot WebSocket Server</h1>
                    <p>WebSocket endpoint: <code>ws://&lt;host&gt;:5000/ws</code></p>
                    <p>Status: <strong style="color: green;">Running ✅</strong></p>
                    <hr>
                    <p><em>Web interface not available (index.html not found)</em></p>
                </body>
            </html>
            """
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "services": {
            "ai": ai_service is not None,
            "tts": tts_service is not None,
            "stt": stt_service is not None,
            "device_manager": device_manager is not None,
            "ota_manager": ota_manager is not None,
            "websocket_handler": ws_handler is not None
        },
        "devices": device_manager.get_device_count() if device_manager else 0,
        "active_connections": ws_handler.get_active_connections_count() if ws_handler else 0
    })


@app.get("/status")
async def get_status():
    """Get detailed server status"""
    if not device_manager:
        return JSONResponse({"error": "Device manager not initialized"}, status_code=503)
    
    stats = device_manager.get_statistics()
    
    return JSONResponse({
        "server": {
            "version": "1.0.0",
            "ai_provider": AI_PROVIDER,
            "ai_model": AI_MODEL,
        },
        "devices": stats,
        "active_connections": ws_handler.get_active_connections_count() if ws_handler else 0,
        "active_device_ids": ws_handler.get_active_devices() if ws_handler else []
    })


# ==============================================================================
# WebSocket Endpoint
# ==============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for device connections
    
    Protocol:
        - Client sends JSON messages
        - Server responds with JSON messages
        - Message types: register, chat, voice, ping, ota_check
    """
    if not ws_handler:
        logger.error("❌ WebSocket handler not initialized")
        await websocket.close(code=1011, reason="Server not ready")
        return
    
    await ws_handler.handle_connection(websocket)


# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting Uvicorn server...")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        access_log=True
    )
