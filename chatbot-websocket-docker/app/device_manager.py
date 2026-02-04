"""
Device Manager - Manages ESP32 device connections and information
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from fastapi import WebSocket


class DeviceManager:
    """Manages ESP32 device connections and metadata"""
    
    def __init__(self):
        """Initialize Device Manager"""
        self.logger = logging.getLogger('DeviceManager')
        self.devices: Dict[str, dict] = {}  # Device metadata
        self.connections: Dict[str, WebSocket] = {}  # Active WebSocket connections
        self.logger.info("📱 Device Manager initialized")
    
    async def register_device(
        self,
        device_id: str,
        device_type: str = "unknown",
        firmware_version: str = "unknown"
    ):
        """Register a new device or update existing device info"""
        self.devices[device_id] = {
            "device_id": device_id,
            "device_type": device_type,
            "firmware_version": firmware_version,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "status": "online"
        }
        
        self.logger.info(f"✅ Device registered: {device_id}")
        return self.devices[device_id]
    
    async def add_connection(self, device_id: str, websocket: WebSocket):
        """Add WebSocket connection for a device"""
        self.connections[device_id] = websocket
        
        # Update device status
        if device_id in self.devices:
            self.devices[device_id]["status"] = "online"
            self.devices[device_id]["last_seen"] = datetime.now().isoformat()
        
        self.logger.info(f"🔌 Connection added: {device_id}")
    
    async def remove_connection(self, device_id: str):
        """Remove WebSocket connection for a device"""
        if device_id in self.connections:
            del self.connections[device_id]
        
        # Update device status
        if device_id in self.devices:
            self.devices[device_id]["status"] = "offline"
            self.devices[device_id]["last_seen"] = datetime.now().isoformat()
        
        self.logger.info(f"🔌 Connection removed: {device_id}")
    
    def get_connection(self, device_id: str) -> Optional[WebSocket]:
        """Get WebSocket connection for a device"""
        return self.connections.get(device_id)
    
    def get_all_connections(self) -> Dict[str, WebSocket]:
        """Get all active WebSocket connections"""
        return self.connections.copy()
    
    def get_device(self, device_id: str) -> Optional[dict]:
        """Get device information"""
        return self.devices.get(device_id)
    
    def get_all_devices(self) -> list:
        """Get all registered devices"""
        return list(self.devices.values())
    
    def update_device_status(self, device_id: str, status: str):
        """Update device status"""
        if device_id in self.devices:
            self.devices[device_id]["status"] = status
            self.devices[device_id]["last_seen"] = datetime.now().isoformat()
            self.logger.info(f"📱 Device {device_id} status updated: {status}")
    
    def is_device_online(self, device_id: str) -> bool:
        """Check if device is online"""
        return device_id in self.connections
    
    def get_online_devices(self) -> list:
        """Get list of online devices"""
        return [
            device for device in self.devices.values()
            if device["device_id"] in self.connections
        ]
    
    def get_device_count(self) -> dict:
        """Get device count statistics"""
        total = len(self.devices)
        online = len(self.connections)
        offline = total - online
        
        return {
            "total": total,
            "online": online,
            "offline": offline
        }
    
    def clear_offline_devices(self, max_age_hours: int = 24):
        """Clear devices that have been offline for too long"""
        from datetime import datetime, timedelta
        
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=max_age_hours)
        
        devices_to_remove = []
        
        for device_id, device in self.devices.items():
            if device["status"] == "offline":
                last_seen = datetime.fromisoformat(device["last_seen"])
                if last_seen < cutoff_time:
                    devices_to_remove.append(device_id)
        
        for device_id in devices_to_remove:
            del self.devices[device_id]
            self.logger.info(f"🗑️ Removed inactive device: {device_id}")
        
        return len(devices_to_remove)

    def get_volume(self) -> int:
        """Get current volume"""
        # Mock implementation
        return 50
    
    def set_volume(self, volume: int):
        """Set volume"""
        self.logger.info(f"🔊 Set volume to {volume}")
        # TODO: Implement actual volume control
    
    def turn_on_light(self):
        """Turn on light"""
        self.logger.info("💡 Light ON")
        # TODO: Implement actual light control
    
    def turn_off_light(self):
        """Turn off light"""
        self.logger.info("🌙 Light OFF")
        # TODO: Implement actual light control