import asyncio
import logging
import os
from aiohttp import web
from websocket_handler import WebSocketHandler
from device_manager import DeviceManager

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ChatbotServer:
    def __init__(self):
        self.app = web.Application()
        self.device_manager = DeviceManager()
        self.ws_handler = WebSocketHandler(self.device_manager)
        
        # Routes
        self.app.router.add_get('/ws', self.ws_handler.handle_websocket)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/devices', self.get_devices)
        
    async def health_check(self, request):
        return web.json_response({
            'status': 'ok',
            'active_devices': len(self.device_manager.devices),
            'version': '1.0.0'
        })
    
    async def get_devices(self, request):
        devices = [
            {
                'device_id': device_id,
                'state': device.state,
                'connected_at': device.connected_at.isoformat()
            }
            for device_id, device in self.device_manager.devices.items()
        ]
        return web.json_response({'devices': devices})

def main():
    logger.info("🚀 Chatbot WebSocket Server starting...")
    
    server = ChatbotServer()
    port = int(os.getenv('PORT', 5000))
    
    web.run_app(server.app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
