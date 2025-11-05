"""
WebSocket Handler
Manages WebSocket connections and message routing
"""
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger('WebSocketHandler')


class WebSocketHandler:
    """
    WebSocket connection handler with proper lifecycle management
    """
    
    def __init__(self, device_manager, ota_manager, ai_service, tts_service, stt_service, conversation_logger=None):
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.conversation_logger = conversation_logger
        self.active_connections: Dict[str, WebSocket] = {}
        
        logger.info("✅ WebSocket Handler initialized")
    
    
    async def handle_connection(self, websocket: WebSocket, device_id: str):
        """
        Handle WebSocket connection lifecycle with proper error handling
        """
        # Accept connection FIRST (CRITICAL!)
        try:
            await websocket.accept()
            logger.info(f"✅ WebSocket accepted for device: {device_id}")
        except Exception as e:
            logger.error(f"❌ Failed to accept WebSocket: {e}")
            return
        
        # Register device
        self.device_manager.register_device(device_id)
        self.active_connections[device_id] = websocket
        
        # Send welcome message
        await self.send_message(device_id, {
            "type": "connection",
            "status": "connected",
            "device_id": device_id,
            "server_time": datetime.now().isoformat(),
            "message": "Connected to School Chatbot Server"
        })
        
        try:
            # Main message loop
            while True:
                try:
                    # Receive message with timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=300.0  # 5 minute timeout
                    )
                    
                    logger.debug(f"📨 Received from {device_id}: {data[:100]}...")
                    
                    # Parse and handle message
                    message = json.loads(data)
                    await self.handle_message(device_id, message)
                    
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    try:
                        await self.send_message(device_id, {
                            "type": "ping",
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception:
                        logger.warning(f"⚠️ Keepalive failed for {device_id}")
                        break
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON from {device_id}: {e}")
                    await self.send_error(device_id, "Invalid JSON format")
                    
                except WebSocketDisconnect:
                    logger.info(f"🔌 Client {device_id} disconnected normally")
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Message handling error for {device_id}: {e}", exc_info=True)
                    # Try to send error, but don't fail if connection is dead
                    try:
                        await self.send_error(device_id, f"Message processing error: {str(e)}")
                    except Exception:
                        logger.debug(f"Could not send error to {device_id} (connection closed)")
                        break
        
        except WebSocketDisconnect:
            logger.info(f"🔌 WebSocket disconnected: {device_id}")
        except Exception as e:
            logger.error(f"❌ Connection error for {device_id}: {e}", exc_info=True)
        finally:
            # Cleanup
            await self.cleanup_connection(device_id)
    
    
    async def cleanup_connection(self, device_id: str):
        """
        Clean up connection resources safely
        """
        try:
            # Remove from active connections
            if device_id in self.active_connections:
                websocket = self.active_connections.pop(device_id)
                
                # Try to close gracefully
                try:
                    if websocket.client_state.value == 1:  # CONNECTED
                        await websocket.close(code=1000, reason="Server cleanup")
                except Exception as e:
                    logger.debug(f"WebSocket already closed for {device_id}: {e}")
            
            # Unregister device
            self.device_manager.unregister_device(device_id)
            
            logger.info(f"🧹 Cleaned up connection for {device_id}")
            
        except Exception as e:
            logger.error(f"❌ Cleanup error for {device_id}: {e}")
    
    
    async def send_message(self, device_id: str, message: dict):
        """
        Send message to device with connection state check
        """
        websocket = self.active_connections.get(device_id)
        
        if not websocket:
            logger.warning(f"⚠️ No active connection for device: {device_id}")
            return False
        
        try:
            # Check if websocket is still connected
            if websocket.client_state.value != 1:  # Not CONNECTED
                logger.warning(f"⚠️ WebSocket not connected for {device_id}")
                return False
            
            # Send message
            message_json = json.dumps(message, ensure_ascii=False)
            await websocket.send_text(message_json)
            
            logger.info(f"📤 Sent '{message.get('type', 'unknown')}' to {device_id}")
            return True
            
        except RuntimeError as e:
            if "close message has been sent" in str(e):
                logger.debug(f"WebSocket closed for {device_id}, cannot send")
            else:
                logger.error(f"❌ Send runtime error for {device_id}: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Send message error for {device_id}: {e}")
            return False
    
    
    async def send_error(self, device_id: str, error_message: str):
        """
        Send error message to device (with safety check)
        """
        # Only send if connection is still active
        if device_id in self.active_connections:
            websocket = self.active_connections[device_id]
            if websocket.client_state.value == 1:  # CONNECTED
                await self.send_message(device_id, {
                    "type": "error",
                    "error": error_message,
                    "timestamp": datetime.now().isoformat()
                })
    
    
    async def handle_message(self, device_id: str, message: dict):
        """
        Route message to appropriate handler based on type
        """
        msg_type = message.get('type', 'unknown')
        
        logger.info(f"📨 Handling '{msg_type}' from {device_id}")
        
        # Route to handlers
        if msg_type == 'chat':
            await self.handle_chat(device_id, message)
        elif msg_type == 'audio':
            await self.handle_audio(device_id, message)
        elif msg_type == 'ota_check':
            await self.handle_ota_check(device_id, message)
        elif msg_type == 'ping':
            await self.handle_ping(device_id)
        elif msg_type == 'status':
            await self.handle_status(device_id, message)
        else:
            logger.warning(f"⚠️ Unknown message type: {msg_type}")
            await self.send_error(device_id, f"Unknown message type: {msg_type}")
    
    
    async def handle_chat(self, device_id: str, message: dict):
        """Handle text chat message"""
        user_text = message.get('text', '').strip()
        
        if not user_text:
            await self.send_error(device_id, "Empty message")
            return
        
        try:
            # Get AI response
            ai_response = await self.ai_service.get_response(
                device_id=device_id,
                user_message=user_text
            )
            
            # Log conversation to MySQL
            if self.conversation_logger:
                try:
                    await self.conversation_logger.log_conversation(
                        device_id=device_id,
                        user_message=user_text,
                        ai_response=ai_response,
                        message_type='text'
                    )
                except Exception as e:
                    logger.warning(f"⚠️ MySQL logging failed: {e}")
            
            # Generate TTS audio
            audio_data = await self.tts_service.text_to_speech(ai_response)
            
            # Send response
            await self.send_message(device_id, {
                "type": "chat_response",
                "text": ai_response,
                "audio": audio_data,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat processing error: {str(e)}")
    
    
    async def handle_audio(self, device_id: str, message: dict):
        """Handle audio (STT) message"""
        audio_data = message.get('audio')
        
        if not audio_data:
            await self.send_error(device_id, "No audio data")
            return
        
        try:
            # Speech-to-Text
            user_text = await self.stt_service.transcribe_audio(audio_data)
            
            if not user_text:
                await self.send_error(device_id, "Could not transcribe audio")
                return
            
            # Get AI response
            ai_response = await self.ai_service.get_response(
                device_id=device_id,
                user_message=user_text
            )
            
            # Log to MySQL
            if self.conversation_logger:
                try:
                    await self.conversation_logger.log_conversation(
                        device_id=device_id,
                        user_message=user_text,
                        ai_response=ai_response,
                        message_type='audio'
                    )
                except Exception as e:
                    logger.warning(f"⚠️ MySQL logging failed: {e}")
            
            # Generate TTS
            response_audio = await self.tts_service.text_to_speech(ai_response)
            
            # Send response
            await self.send_message(device_id, {
                "type": "audio_response",
                "transcribed_text": user_text,
                "response_text": ai_response,
                "audio": response_audio,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}", exc_info=True)
            await self.send_error(device_id, f"Audio processing error: {str(e)}")
    
    
    async def handle_ota_check(self, device_id: str, message: dict):
        """Handle OTA update check"""
        current_version = message.get('current_version', '0.0.0')
        
        update_info = self.ota_manager.check_for_update(current_version)
        
        await self.send_message(device_id, {
            "type": "ota_response",
            **update_info
        })
    
    
    async def handle_ping(self, device_id: str):
        """Handle ping/keepalive"""
        await self.send_message(device_id, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
    
    
    async def handle_status(self, device_id: str, message: dict):
        """Handle device status update"""
        status_data = message.get('data', {})
        self.device_manager.update_device_status(device_id, status_data)
        logger.info(f"📊 Device {device_id} status updated")
    
    
    def get_active_connections_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    
    def get_active_devices(self) -> list:
        """Get list of active device IDs"""
        return list(self.active_connections.keys())
