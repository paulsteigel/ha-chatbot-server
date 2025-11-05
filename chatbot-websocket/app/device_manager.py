"""
Device Manager
Manages connected ESP32 devices and their states
"""
import logging
from datetime import datetime
from typing import Dict, Optional, Any


class DeviceManager:
    """Manage connected ESP32 devices"""
    
    def __init__(self):
        """Initialize device manager"""
        self.logger = logging.getLogger('DeviceManager')
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.logger.info("📱 Device Manager initialized")
    
    def register_device(self, device_id: str, device_type: str = 'unknown') -> None:
        """
        Register a new device
        
        Args:
            device_id: Unique device identifier
            device_type: Type of device (esp32, web-browser, etc.)
        """
        self.devices[device_id] = {
            'device_type': device_type,
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0,
            'voice_count': 0
        }
        
        self.logger.info(f"✅ Device registered: {device_id} (Type: {device_type})")
        self.logger.info(f"   Total devices: {len(self.devices)}")
    
    def unregister_device(self, device_id: str) -> None:
        """
        Unregister a device
        
        Args:
            device_id: Device identifier
        """
        if device_id in self.devices:
            device_info = self.devices[device_id]
            duration = datetime.now() - device_info['connected_at']
            
            self.logger.info(f"❌ Device unregistered: {device_id}")
            self.logger.info(f"   Session duration: {duration}")
            self.logger.info(f"   Messages: {device_info['message_count']}, Voice: {device_info['voice_count']}")
            
            del self.devices[device_id]
            self.logger.info(f"   Remaining devices: {len(self.devices)}")
        else:
            self.logger.warning(f"⚠️ Tried to unregister unknown device: {device_id}")
    
    def update_activity(self, device_id: str, activity_type: str = 'message') -> None:
        """
        Update device last activity timestamp
        
        Args:
            device_id: Device identifier
            activity_type: Type of activity ('message' or 'voice')
        """
        if device_id in self.devices:
            self.devices[device_id]['last_activity'] = datetime.now()
            
            if activity_type == 'message':
                self.devices[device_id]['message_count'] += 1
            elif activity_type == 'voice':
                self.devices[device_id]['voice_count'] += 1
                
            self.logger.debug(f"📊 Activity updated for {device_id}: {activity_type}")
        else:
            self.logger.warning(f"⚠️ Activity update for unknown device: {device_id}")
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device information
        
        Args:
            device_id: Device identifier
        
        Returns:
            Device info dict or None if not found
        """
        return self.devices.get(device_id)
    
    def get_device_count(self) -> int:
        """Get number of connected devices"""
        return len(self.devices)
    
    def get_all_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get all connected devices"""
        return self.devices.copy()
    
    def is_device_registered(self, device_id: str) -> bool:
        """Check if device is registered"""
        return device_id in self.devices
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about all devices
        
        Returns:
            Statistics dictionary
        """
        total_messages = sum(d['message_count'] for d in self.devices.values())
        total_voice = sum(d['voice_count'] for d in self.devices.values())
        
        device_types = {}
        for device in self.devices.values():
            dtype = device['device_type']
            device_types[dtype] = device_types.get(dtype, 0) + 1
        
        return {
            'total_devices': len(self.devices),
            'total_messages': total_messages,
            'total_voice': total_voice,
            'device_types': device_types,
            'devices': list(self.devices.keys())
        }
