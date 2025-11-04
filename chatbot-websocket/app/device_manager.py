import logging
from datetime import datetime
from typing import Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DeviceInfo:
    device_id: str
    ws: object
    state: str  # 'idle', 'listening', 'processing', 'speaking'
    connected_at: datetime
    last_activity: datetime

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}
        
    def register_device(self, device_id: str, ws):
        """Register new device"""
        self.devices[device_id] = DeviceInfo(
            device_id=device_id,
            ws=ws,
            state='idle',
            connected_at=datetime.now(),
            last_activity=datetime.now()
        )
        logger.info(f"📱 Device registered: {device_id}")
        
    def disconnect_device(self, device_id: str):
        """Disconnect device"""
        if device_id in self.devices:
            del self.devices[device_id]
            logger.info(f"📱 Device disconnected: {device_id}")
            
    def update_state(self, device_id: str, state: str):
        """Update device state"""
        if device_id in self.devices:
            self.devices[device_id].state = state
            self.devices[device_id].last_activity = datetime.now()
            
    def get_device(self, device_id: str) -> DeviceInfo:
        """Get device info"""
        return self.devices.get(device_id)
