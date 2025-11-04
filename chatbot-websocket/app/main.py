import asyncio
import logging
import os
from aiohttp import web
from websocket_handler import WebSocketHandler
from device_manager import DeviceManager
from ota_manager import OTAManager

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ChatbotServer:
    def __init__(self):
        self.app = web.Application(client_max_size=50*1024*1024)  # 50MB for firmware
        self.device_manager = DeviceManager()
        self.ws_handler = WebSocketHandler(self.device_manager)
        self.ota_manager = OTAManager()
        
        # Routes
        self.app.router.add_get('/ws', self.ws_handler.handle_websocket)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/devices', self.get_devices)
        
        # OTA routes
        self.app.router.add_post('/api/firmware/upload', self.ota_manager.upload_firmware)
        self.app.router.add_get('/api/firmware/list', self.ota_manager.list_firmware)
        self.app.router.add_get('/firmware/{filename}', self.ota_manager.download_firmware)
        self.app.router.add_delete('/api/firmware/{filename}', self.ota_manager.delete_firmware)
        
        # Static files (UI)
        self.app.router.add_get('/', self.serve_ui)
        
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
                'connected_at': device.connected_at.isoformat(),
                'last_activity': device.last_activity.isoformat()
            }
            for device_id, device in self.device_manager.devices.items()
        ]
        return web.json_response({'devices': devices})
    
    async def serve_ui(self, request):
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>School Chatbot Server</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 4px; }
        .device { padding: 10px; margin: 5px 0; background: #f9f9f9; border-radius: 4px; }
        .btn { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        #firmware-list { margin-top: 10px; }
        .firmware-item { padding: 8px; margin: 5px 0; background: #e9ecef; border-radius: 4px; display: flex; justify-content: space-between; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 School Chatbot Server</h1>
        
        <div class="section">
            <h2>📱 Connected Devices</h2>
            <div id="devices">Loading...</div>
        </div>
        
        <div class="section">
            <h2>🔄 OTA Firmware Update</h2>
            <input type="file" id="firmware-file" accept=".bin">
            <button class="btn" onclick="uploadFirmware()">Upload Firmware</button>
            <div id="upload-status"></div>
            <div id="firmware-list"></div>
        </div>
    </div>
    
    <script>
        async function loadDevices() {
            const response = await fetch('/devices');
            const data = await response.json();
            const devicesDiv = document.getElementById('devices');
            
            if (data.devices.length === 0) {
                devicesDiv.innerHTML = '<p>No devices connected</p>';
            } else {
                devicesDiv.innerHTML = data.devices.map(d => 
                    `<div class="device">
                        <strong>${d.device_id}</strong> - ${d.state}<br>
                        <small>Connected: ${new Date(d.connected_at).toLocaleString()}</small>
                    </div>`
                ).join('');
            }
        }
        
        async function loadFirmware() {
            const response = await fetch('/api/firmware/list');
            const data = await response.json();
            const listDiv = document.getElementById('firmware-list');
            
            if (data.files.length === 0) {
                listDiv.innerHTML = '<p>No firmware files</p>';
            } else {
                listDiv.innerHTML = data.files.map(f => 
                    `<div class="firmware-item">
                        <span>${f.filename} (${(f.size/1024/1024).toFixed(2)} MB)</span>
                        <button class="btn" onclick="deleteFirmware('${f.filename}')">Delete</button>
                    </div>`
                ).join('');
            }
        }
        
        async function uploadFirmware() {
            const fileInput = document.getElementById('firmware-file');
            const file = fileInput.files[0];
            
            if (!file) {
                alert('Please select a firmware file');
                return;
            }
            
            const statusDiv = document.getElementById('upload-status');
            statusDiv.innerHTML = '<p>Uploading...</p>';
            
            const formData = new FormData();
            formData.append('firmware', file);
            
            try {
                const response = await fetch('/api/firmware/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.innerHTML = `<p style="color:green;">✅ Uploaded: ${data.filename}</p>`;
                    loadFirmware();
                } else {
                    statusDiv.innerHTML = `<p style="color:red;">❌ Error: ${data.error}</p>`;
                }
            } catch (error) {
                statusDiv.innerHTML = `<p style="color:red;">❌ Error: ${error}</p>`;
            }
        }
        
        async function deleteFirmware(filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            
            await fetch(`/api/firmware/${filename}`, { method: 'DELETE' });
            loadFirmware();
        }
        
        // Auto refresh
        setInterval(loadDevices, 3000);
        loadDevices();
        loadFirmware();
    </script>
</body>
</html>
        """
        return web.Response(text=html, content_type='text/html')

def main():
    logger.info("🚀 Chatbot WebSocket Server starting...")
    
    server = ChatbotServer()
    port = int(os.getenv('PORT', 5000))
    
    web.run_app(server.app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
