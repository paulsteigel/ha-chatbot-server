import os
import logging
import asyncio
from aiohttp import web
from pathlib import Path

logger = logging.getLogger(__name__)

class OTAManager:
    def __init__(self):
        self.firmware_dir = Path('/data/firmware')
        self.firmware_dir.mkdir(exist_ok=True)
        
    async def upload_firmware(self, request):
        """Handle firmware upload"""
        try:
            reader = await request.multipart()
            field = await reader.next()
            
            if field.name != 'firmware':
                return web.json_response({'error': 'Invalid field name'}, status=400)
            
            filename = field.filename
            if not filename.endswith('.bin'):
                return web.json_response({'error': 'Only .bin files allowed'}, status=400)
            
            filepath = self.firmware_dir / filename
            
            size = 0
            with open(filepath, 'wb') as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)
            
            logger.info(f"✅ Firmware uploaded: {filename} ({size} bytes)")
            
            return web.json_response({
                'success': True,
                'filename': filename,
                'size': size,
                'url': f'/firmware/{filename}'
            })
            
        except Exception as e:
            logger.error(f"Firmware upload error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def list_firmware(self, request):
        """List available firmware files"""
        try:
            files = []
            for filepath in self.firmware_dir.glob('*.bin'):
                stat = filepath.stat()
                files.append({
                    'filename': filepath.name,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'url': f'/firmware/{filepath.name}'
                })
            
            return web.json_response({'files': files})
            
        except Exception as e:
            logger.error(f"List firmware error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def download_firmware(self, request):
        """Serve firmware file"""
        filename = request.match_info['filename']
        filepath = self.firmware_dir / filename
        
        if not filepath.exists():
            return web.Response(status=404, text='Firmware not found')
        
        return web.FileResponse(filepath)
    
    async def delete_firmware(self, request):
        """Delete firmware file"""
        filename = request.match_info['filename']
        filepath = self.firmware_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            logger.info(f"🗑️ Firmware deleted: {filename}")
            return web.json_response({'success': True})
        
        return web.Response(status=404, text='Firmware not found')
