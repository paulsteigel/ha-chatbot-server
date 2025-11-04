import logging
import json
import asyncio
from aiohttp import web
from .audio_processor import AudioProcessor  # ← Fix: Thêm dấu chấm

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, app):
        self.app = app
        self.active_connections = {}
        logger.info("🔌 WebSocket handler initialized")
        
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        device_id = request.rel_url.query.get('device_id', 'unknown')
        logger.info(f"📱 Device connected: {device_id}")
        
        # Register device
        self.active_connections[device_id] = ws
        self.app['devices'].register_device(device_id, ws)
        
        # Create audio processor for this connection
        audio_processor = AudioProcessor(
            stt_service=self.app['stt'],
            tts_service=self.app['tts'],
            ai_service=self.app['ai'],
            device_id=device_id
        )
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    # Handle audio data
                    await audio_processor.process_audio(msg.data, ws)
                    
                elif msg.type == web.WSMsgType.TEXT:
                    # Handle text commands
                    try:
                        data = json.loads(msg.data)
                        await self.handle_command(data, ws, device_id)
                    except json.JSONDecodeError:
                        logger.error(f"❌ Invalid JSON from {device_id}")
                        
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f'❌ WebSocket error: {ws.exception()}')
                    
        except Exception as e:
            logger.error(f"❌ Error handling connection: {e}", exc_info=True)
            
        finally:
            # Cleanup
            if device_id in self.active_connections:
                del self.active_connections[device_id]
            self.app['devices'].unregister_device(device_id)
            logger.info(f"📱 Device disconnected: {device_id}")
            
        return ws
    
    async def handle_command(self, data, ws, device_id):
        """Handle text commands"""
        cmd = data.get('type')
        
        if cmd == 'ping':
            await ws.send_json({'type': 'pong'})
            
        elif cmd == 'status':
            await ws.send_json({
                'type': 'status',
                'device_id': device_id,
                'connected': True
            })
            
        elif cmd == 'ota_check':
            # Check for firmware updates
            latest = self.app['ota'].get_latest_firmware()
            await ws.send_json({
                'type': 'ota_available',
                'version': latest['version'] if latest else None
            })
            
        else:
            logger.warning(f"⚠️  Unknown command: {cmd}")
