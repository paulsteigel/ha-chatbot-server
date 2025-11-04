import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manage connected ESP32 devices"""
    
    def __init__(self):
        """Initialize device manager"""
        self.devices = {}  # device_id -> device_info
        logger.info("📱 Device Manager initialized")
    
    def register_device(self, device_id, websocket):
        """Register a new device"""
        self.devices[device_id] = {
            'websocket': websocket,
            'connected_at': datetime.now(),
            'last_activity': datetime.now()
        }
        logger.info(f"✅ Device registered: {device_id}")
    
    def unregister_device(self, device_id):
        """Unregister a device"""
        if device_id in self.devices:
            del self.devices[device_id]
            logger.info(f"❌ Device unregistered: {device_id}")
    
    def update_activity(self, device_id):
        """Update device last activity"""
        if device_id in self.devices:
            self.devices[device_id]['last_activity'] = datetime.now()
    
    def get_device_count(self):
        """Get number of connected devices"""
        return len(self.devices)
