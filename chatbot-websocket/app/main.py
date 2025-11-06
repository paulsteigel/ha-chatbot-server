"""
School Chatbot WebSocket Server
Main FastAPI application with WebSocket support for ESP32 devices
"""
import logging
#import asyncio
import os
import json
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
from app.conversation_logger import ConversationLogger
from app.config import SYSTEM_PROMPT, AI_CONFIG, TTS_CONFIG, STT_CONFIG, AI_MODELS

# ==============================================================================
# Configuration Helper - WITH NULL HANDLING
# ==============================================================================

def get_config(key: str, default=None):
    """
    Get configuration value from Home Assistant options.json or environment
    
    Priority:
    1. Home Assistant options.json (when running as HA add-on)
    2. Environment variable
    3. Default value
    """
    # Try Home Assistant options first
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        try:
            with open(options_file, 'r') as f:
                options = json.load(f)
                if key in options:
                    value = options[key]
                    # ✅ FIX: Handle "null" string and None
                    if value not in [None, "", "null", "None"]:
                        return value
        except Exception:
            pass  # Silently fail, will try environment
    
    # Fallback to environment variable
    env_key = key.upper()
    env_value = os.getenv(env_key)
    # ✅ FIX: Handle "null" string from env
    if env_value not in [None, "", "null", "None"]:
        return env_value
    
    return default


def safe_int(value, default: int) -> int:
    """Safely convert value to int, handle null/None."""
    if value is None or value == "" or value == "null" or value == "None":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float) -> float:
    """Safely convert value to float, handle null/None."""
    if value is None or value == "" or value == "null" or value == "None":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ==============================================================================
# Configuration
# ==============================================================================

# Logging setup first
LOG_LEVEL = get_config('log_level', 'INFO').upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Main')

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))

# ✅ AI CONFIGURATION - AUTO MODEL SELECTION
AI_PROVIDER = get_config('ai_provider', 'deepseek')

# Auto-select correct model for provider
if AI_PROVIDER.lower() == 'openai':
    DEFAULT_MODEL = AI_MODELS.get('openai', 'gpt-4o-mini')
elif AI_PROVIDER.lower() == 'deepseek':
    DEFAULT_MODEL = AI_MODELS.get('deepseek', 'deepseek-chat')
else:
    DEFAULT_MODEL = 'gpt-4o-mini'

# Allow manual override
AI_MODEL = get_config('ai_model', DEFAULT_MODEL)

logger.info("=" * 80)
logger.info("🤖 AI CONFIGURATION")
logger.info("=" * 80)
logger.info(f"   Provider: {AI_PROVIDER}")
logger.info(f"   Model (auto): {DEFAULT_MODEL}")
logger.info(f"   Model (final): {AI_MODEL}")
if AI_MODEL != DEFAULT_MODEL:
    logger.warning(f"   ⚠️  Manual override detected!")
logger.info("=" * 80)

# ✅ SYSTEM_PROMPT - Allow override
SYSTEM_PROMPT_OVERRIDE = get_config('system_prompt', None)
if SYSTEM_PROMPT_OVERRIDE and len(SYSTEM_PROMPT_OVERRIDE) > 50:
    FINAL_SYSTEM_PROMPT = SYSTEM_PROMPT_OVERRIDE
    logger.info("💬 Using CUSTOM system prompt from Home Assistant")
else:
    FINAL_SYSTEM_PROMPT = SYSTEM_PROMPT
    logger.info("💬 Using DEFAULT system prompt from config.py")

# ✅ FIX: Chat configuration with safe parsing
CHAT_TEMPERATURE = safe_float(
    get_config('temperature', AI_CONFIG.get("temperature", 0.7)),
    0.7
)
CHAT_MAX_TOKENS = safe_int(
    get_config('max_tokens', AI_CONFIG.get("max_tokens", 300)),
    300
)
CHAT_MAX_CONTEXT = safe_int(
    get_config('max_context_messages', AI_CONFIG.get("max_context_messages", 10)),
    10
)

# API Keys
OPENAI_API_KEY = get_config('openai_api_key', '')
OPENAI_BASE_URL = get_config('openai_base_url', 'https://api.openai.com/v1')
DEEPSEEK_API_KEY = get_config('deepseek_api_key', '')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
GROQ_API_KEY = get_config('groq_api_key', '')

# MySQL configuration
MYSQL_URL = get_config('mysql_url', '')

# TTS configuration
TTS_VOICE = get_config('tts_voice_vi', TTS_CONFIG.get("vietnamese_voice", "nova"))

# ✅ LOG FULL CONFIGURATION
config_source = "Home Assistant" if os.path.exists("/data/options.json") else "Environment"
logger.info("=" * 80)
logger.info("📋 FULL CONFIGURATION")
logger.info("=" * 80)
logger.info(f"📂 Config Source: {config_source}")
logger.info(f"🤖 AI Provider: {AI_PROVIDER}")
logger.info(f"🧠 AI Model: {AI_MODEL}")
logger.info(f"💬 System Prompt: {FINAL_SYSTEM_PROMPT[:80]}...")
logger.info(f"🌡️  Temperature: {CHAT_TEMPERATURE}")
logger.info(f"📏 Max Tokens: {CHAT_MAX_TOKENS}")
logger.info(f"💬 Max Context: {CHAT_MAX_CONTEXT}")
logger.info(f"💾 MySQL: {'✅' if MYSQL_URL else '❌'}")
logger.info(f"📊 Log Level: {LOG_LEVEL}")
logger.info("=" * 80)



# ==============================================================================
# Service Instances (Global)
# ==============================================================================

ai_service = None
tts_service = None
stt_service = None
device_manager = None
ota_manager = None
ws_handler = None
conversation_logger = None


# ==============================================================================
# Lifespan Context Manager
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown
    """
    global device_manager, ota_manager, ai_service, tts_service, stt_service, ws_handler, conversation_logger
    
    logger.info("=" * 80)
    logger.info("🚀 SCHOOL CHATBOT WEBSOCKET SERVER")
    logger.info("=" * 80)
    
    try:
        # Initialize Device Manager
        logger.info("📱 Initializing Device Manager...")
        device_manager = DeviceManager()
        
        # Initialize OTA Manager
        logger.info("📦 Initializing OTA Manager...")
        ota_manager = OTAManager()
        
        # Initialize AI Service
        logger.info(f"🤖 Initializing AI Service ({AI_PROVIDER})...")
        ai_service = AIService(
            api_key=DEEPSEEK_API_KEY if AI_PROVIDER == 'deepseek' else OPENAI_API_KEY,
            base_url=DEEPSEEK_BASE_URL if AI_PROVIDER == 'deepseek' else OPENAI_BASE_URL,
            model=AI_MODEL,
            system_prompt=SYSTEM_PROMPT,
            temperature=CHAT_TEMPERATURE,
            max_tokens=CHAT_MAX_TOKENS,
            max_context=CHAT_MAX_CONTEXT
        )
        
        # Initialize TTS Service
        logger.info("🔊 Initializing TTS Service...")
        tts_service = TTSService()
        
        # Initialize STT Service
        logger.info("🎤 Initializing STT Service...")
        stt_service = STTService(
            api_key=GROQ_API_KEY if GROQ_API_KEY else OPENAI_API_KEY,
            base_url="https://api.groq.com/openai/v1" if GROQ_API_KEY else OPENAI_BASE_URL,
            model="whisper-large-v3" if GROQ_API_KEY else "whisper-1"
        )
        
        # Initialize Conversation Logger (MySQL)
        if MYSQL_URL:
            try:
                logger.info("💾 Initializing Conversation Logger...")
                conversation_logger = ConversationLogger(MYSQL_URL)
                await conversation_logger.connect()
            except Exception as e:
                logger.warning(f"⚠️ MySQL logger disabled: {e}")
                conversation_logger = None
        else:
            logger.info("⚠️ MYSQL_URL not set, conversation logging disabled")
        
        # Initialize WebSocket Handler
        logger.info("🔌 Initializing WebSocket Handler...")
        ws_handler = WebSocketHandler(
            device_manager=device_manager,
            ota_manager=ota_manager,
            ai_service=ai_service,
            tts_service=tts_service,
            stt_service=stt_service,
            conversation_logger=conversation_logger
        )
        
        logger.info("=" * 80)
        logger.info("✅ ALL SERVICES INITIALIZED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"🌐 Server listening on: {HOST}:{PORT}")
        logger.info(f"📡 WebSocket endpoint: ws://{HOST}:{PORT}/ws")
        logger.info(f"🌍 Web interface: http://{HOST}:{PORT}/")
        logger.info("=" * 80)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ STARTUP FAILED: {e}", exc_info=True)
        raise
    
    finally:
        logger.info("🛑 Shutting down services...")
        
        # Close MySQL connection
        if conversation_logger:
            try:
                await conversation_logger.close()
                logger.info("💾 MySQL connection closed")
            except Exception as e:
                logger.error(f"❌ MySQL close error: {e}")
        
        logger.info("✅ Shutdown complete")


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
    # Get device count safely
    device_count = 0
    if device_manager and hasattr(device_manager, 'get_device_count'):
        device_count = device_manager.get_device_count()
    elif device_manager and hasattr(device_manager, 'devices'):
        device_count = len(device_manager.devices)
    
    # Get active connections count safely
    active_connections = 0
    if ws_handler and hasattr(ws_handler, 'get_active_connections_count'):
        active_connections = ws_handler.get_active_connections_count()
    elif ws_handler and hasattr(ws_handler, 'active_connections'):
        active_connections = len(ws_handler.active_connections)
    
    return JSONResponse({
        "status": "healthy",
        "services": {
            "ai": ai_service is not None,
            "tts": tts_service is not None,
            "stt": stt_service is not None,
            "device_manager": device_manager is not None,
            "ota_manager": ota_manager is not None,
            "websocket_handler": ws_handler is not None,
            "conversation_logger": conversation_logger is not None
        },
        "devices": device_count,
        "active_connections": active_connections
    })

# Thêm vào main.py sau endpoint /health

@app.get("/api/mysql/status")
async def mysql_status():
    """
    ✅ CHECK MYSQL LOGGING STATUS
    Endpoint để monitor MySQL logging health
    """
    if not conversation_logger:
        return JSONResponse({
            "status": "disabled",
            "message": "MySQL logging not configured",
            "help": "Set MYSQL_URL in Home Assistant config"
        })
    
    try:
        # Get stats
        stats = conversation_logger.get_stats()
        
        # Test connection
        pool_info = {
            "available": False,
            "size": 0,
            "freesize": 0,
            "maxsize": 0
        }
        
        if conversation_logger.pool:
            try:
                # Quick connection test
                async with asyncio.timeout(3):
                    async with conversation_logger.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            await cursor.fetchone()
                
                pool_info = {
                    "available": True,
                    "size": conversation_logger.pool.size,
                    "freesize": conversation_logger.pool.freesize,
                    "maxsize": conversation_logger.pool.maxsize
                }
            except Exception as e:
                logger.error(f"MySQL status check failed: {e}")
        
        return JSONResponse({
            "status": stats.get('health', 'unknown'),
            "pool": pool_info,
            "stats": {
                "total_attempts": stats.get('total_attempts', 0),
                "successful_logs": stats.get('successful_logs', 0),
                "failed_logs": stats.get('failed_logs', 0),
                "success_rate": f"{stats.get('success_rate', 0):.1f}%",
                "consecutive_failures": stats.get('consecutive_failures', 0)
            },
            "last_success": stats.get('last_success'),
            "last_error": stats.get('last_error'),
            "last_error_time": stats.get('last_error_time'),
            "recommendation": _get_recommendation(stats)
        })
    
    except Exception as e:
        logger.error(f"MySQL status endpoint error: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


def _get_recommendation(stats: dict) -> str:
    """Get recommendation based on stats"""
    health = stats.get('health', 'unknown')
    failures = stats.get('consecutive_failures', 0)
    success_rate = stats.get('success_rate', 100)
    
    if health == 'disconnected':
        return "❌ MySQL disconnected. Check MySQL addon is running."
    
    if health == 'critical':
        return f"🚨 {failures} consecutive failures! MySQL may be down or overloaded."
    
    if health == 'degraded':
        return f"⚠️ {failures} recent failures. Monitor closely."
    
    if success_rate < 95:
        return f"⚠️ Low success rate ({success_rate:.1f}%). Check MySQL performance."
    
    return "✅ All systems operational."


@app.get("/status")
async def get_status():
    """Get detailed server status"""
    if not device_manager:
        return JSONResponse({"error": "Device manager not initialized"}, status_code=503)
    
    # Get statistics safely
    stats = {}
    if hasattr(device_manager, 'get_statistics'):
        stats = device_manager.get_statistics()
    elif hasattr(device_manager, 'devices'):
        stats = {
            "total_devices": len(device_manager.devices),
            "devices": list(device_manager.devices.keys())
        }
    
    # Get active connections
    active_connections = 0
    active_devices = []
    if ws_handler:
        if hasattr(ws_handler, 'get_active_connections_count'):
            active_connections = ws_handler.get_active_connections_count()
        elif hasattr(ws_handler, 'active_connections'):
            active_connections = len(ws_handler.active_connections)
        
        if hasattr(ws_handler, 'get_active_devices'):
            active_devices = ws_handler.get_active_devices()
        elif hasattr(ws_handler, 'active_connections'):
            active_devices = list(ws_handler.active_connections.keys())
    
    return JSONResponse({
        "server": {
            "version": "1.0.0",
            "ai_provider": AI_PROVIDER,
            "ai_model": AI_MODEL,
            "mysql_logging": conversation_logger is not None
        },
        "devices": stats,
        "active_connections": active_connections,
        "active_device_ids": active_devices
    })


@app.get("/api/conversations")
async def get_conversations(device_id: str = None, limit: int = 50):
    """Get conversation history from MySQL"""
    if not conversation_logger:
        return JSONResponse({
            "error": "Conversation logging not enabled"
        }, status_code=503)
    
    try:
        history = await conversation_logger.get_history(device_id, limit)
        return JSONResponse({
            "conversations": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"❌ Get conversations error: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)


# ==============================================================================
# WebSocket Endpoint
# ==============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for device connections"""
    #device_id = f"web-{id(websocket)}"
    #await ws_handler.handle_connection(websocket, device_id)
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
