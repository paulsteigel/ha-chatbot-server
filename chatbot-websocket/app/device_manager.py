import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DeviceManager:
    def __init__(self):
        self.devices = {}
        logger.info("📱 Device manager initialized")
    
    def register_device(self, device_id, ws):
        """Register a device"""
        self.devices[device_id] = {
            'ws': ws,
            'connected_at': datetime.now(),
            'last_activity': datetime.now()
        }
        logger.info(f"✅ Device registered: {device_id}")
    
    def unregister_device(self, device_id):
        """Unregister a device"""
        if device_id in self.devices:
            del self.devices[device_id]
            logger.info(f"❌ Device unregistered: {device_id}")
    
    def get_device(self, device_id):
        """Get device info"""
        return self.devices.get(device_id)
    
    def list_devices(self):
        """List all connected devices"""
        return list(self.devices.keys())
