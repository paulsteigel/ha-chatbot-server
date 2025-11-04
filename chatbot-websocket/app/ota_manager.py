import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class OTAManager:
    def __init__(self, firmware_dir='/data/firmware'):
        self.firmware_dir = Path(firmware_dir)
        self.firmware_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📦 OTA manager initialized: {firmware_dir}")
    
    def get_latest_firmware(self):
        """Get latest firmware info"""
        try:
            firmware_files = list(self.firmware_dir.glob('*.bin'))
            if not firmware_files:
                return None
            
            # Get most recent
            latest = max(firmware_files, key=os.path.getctime)
            
            return {
                'version': latest.stem,
                'path': str(latest),
                'size': latest.stat().st_size
            }
        except Exception as e:
            logger.error(f"❌ Error getting firmware: {e}")
            return None
    
    def upload_firmware(self, file_data, version):
        """Upload new firmware"""
        try:
            firmware_path = self.firmware_dir / f"{version}.bin"
            firmware_path.write_bytes(file_data)
            logger.info(f"✅ Firmware uploaded: {version}")
            return True
        except Exception as e:
            logger.error(f"❌ Firmware upload error: {e}")
            return False
