"""
WebSocket Handler - Handles WebSocket connections and messages
"""

import logging
import json
import time
import base64
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.command_detector import CommandDetector


class WebSocketHandler:
    """WebSocket handler for managing device connections and messages"""
    
    def __init__(
        self, 
        device_manager, 
        ota_manager, 
        ai_service, 
        tts_service, 
        stt_service,
        conversation_logger=None
    ):
        """Initialize WebSocket Handler"""
        self.logger = logging.getLogger('WebSocketHandler')
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.conversation_logger = conversation_logger
        self.command_detector = CommandDetector()
        self.logger.info("🔌 WebSocket Handler initialized")
    
    async def handle_connection(self, websocket: WebSocket, device_id: str):
        """Handle WebSocket connection"""
        try:
            # STEP 1: Accept connection first
            await websocket.accept()
            self.logger.info(f"📱 New WebSocket connection: {device_id}")
            
            # STEP 2: Store connection
            await self.device_manager.add_connection(device_id, websocket)
            
            # STEP 3: Handle messages
            while True:
                try:
                    # Check if websocket is still connected
                    if websocket.client_state.name != "CONNECTED":
                        self.logger.warning(f"⚠️ WebSocket not connected: {device_id}")
                        break
                    
                    # Receive message with timeout
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=300.0  # 5 minutes timeout
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⏱️ Timeout waiting for message from {device_id}")
                        # Send ping to check if still alive
                        await self.send_message(device_id, {"type": "ping"})
                        continue
                    
                    message = json.loads(data)
                    
                    self.logger.info(f"📨 Message from {device_id}: {message.get('type', 'unknown')}")
                    
                    # Route message to appropriate handler
                    await self.route_message(device_id, message)
                    
                except WebSocketDisconnect:
                    self.logger.info(f"📱 WebSocket disconnected: {device_id}")
                    break
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ JSON decode error: {e}")
                    await self.send_error(device_id, "Invalid JSON format")
                    
                except Exception as e:
                    self.logger.error(f"❌ Message handling error: {e}", exc_info=True)
                    # Don't send error if connection is already closed
                    if websocket.client_state.name == "CONNECTED":
                        await self.send_error(device_id, str(e))
                    else:
                        break
                    
        except RuntimeError as e:
            if "WebSocket is not connected" in str(e):
                self.logger.warning(f"⚠️ WebSocket connection failed for {device_id}")
            else:
                self.logger.error(f"❌ Connection error: {e}", exc_info=True)
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}", exc_info=True)
            
        finally:
            # STEP 4: Cleanup
            await self.device_manager.remove_connection(device_id)
            self.logger.info(f"📱 Connection closed: {device_id}")
  
    async def route_message(self, device_id: str, message: Dict):
        """Route message to appropriate handler"""
        message_type = message.get("type")
        
        handlers = {
            "register": self.handle_register,
            "text": self.handle_text,
            "chat": self.handle_chat,
            "voice": self.handle_voice,
            "ping": self.handle_ping,
            "get_devices": self.handle_get_devices,
            "clear_history": self.handle_clear_history,
        }
        
        handler = handlers.get(message_type)
        
        if handler:
            message["device_id"] = device_id
            await handler(message)
        else:
            self.logger.warning(f"⚠️ Unknown message type: {message_type}")
            await self.send_error(device_id, f"Unknown message type: {message_type}")
    
    async def handle_register(self, data: Dict):
        """Handle device registration"""
        try:
            device_id = data.get("device_id")
            device_type = data.get("device_type", "unknown")
            firmware_version = data.get("firmware_version", "unknown")
            
            self.logger.info(f"✅ Registering device: {device_id}")
            self.logger.info(f"   Type: {device_type}")
            self.logger.info(f"   Firmware: {firmware_version}")
            
            # Register device
            await self.device_manager.register_device(
                device_id=device_id,
                device_type=device_type,
                firmware_version=firmware_version
            )
            
            # Send registration confirmation
            await self.send_message(device_id, {
                "type": "registered",
                "device_id": device_id,
                "server_version": "1.0.0"
            })
            
        except Exception as e:
            self.logger.error(f"❌ Registration error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Registration error: {e}")
    
    async def handle_chat(self, data: Dict):
        """Handle chat message from web interface"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Chat from {device_id}: {text}")
            
            # Get device info
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ✅ GET AI RESPONSE WITH LANGUAGE
            ai_response, language = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            )
            
            if not ai_response:
                await self.send_error(device_id, "AI service error")
                return
            
            # ✅ GENERATE TTS WITH DETECTED LANGUAGE
            audio_base64 = await self.tts_service.synthesize(ai_response, language)
            
            # Send response
            await self.send_message(device_id, {
                "type": "chat_response",
                "text": ai_response,
                "audio": audio_base64,
                "audio_format": "mp3",
                "language": language  # ← Send language to frontend
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat error: {e}")
    
    async def handle_text(self, data: Dict):
        """Handle text message from ESP32"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Text from {device_id}: {text}")
            
            # Get device info
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ✅ GET AI RESPONSE WITH LANGUAGE
            ai_response, language = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            )
            
            if not ai_response:
                await self.send_error(device_id, "AI service error")
                return
            
            # Send text response
            await self.send_message(device_id, {
                "type": "text",
                "text": ai_response,
                "language": language
            })
            
            # ✅ GENERATE AUDIO WITH DETECTED LANGUAGE
            audio_base64 = await self.tts_service.synthesize(ai_response, language)
            
            if audio_base64:
                # Send audio response
                await self.send_message(device_id, {
                    "type": "audio",
                    "audio": audio_base64,
                    "format": "mp3",
                    "language": language
                })
            
        except Exception as e:
            self.logger.error(f"❌ Text error: {e}", exc_info=True)
            await self.send_error(device_id, f"Text error: {e}")
    
    async def handle_voice(self, data: Dict):
        """Handle voice message with streaming TTS"""
        try:
            device_id = data.get("device_id")
            audio_base64 = data.get("audio")
            stt_language = data.get("language", "vi")
            
            if not audio_base64:
                await self.send_error(device_id, "Missing audio data")
                return
            
            self.logger.info(f"🎤 Voice from {device_id}")
            
            # STEP 1: TRANSCRIBE
            audio_data = base64.b64decode(audio_base64)
            text = await self.stt_service.transcribe(audio_data, stt_language)
            
            if not text:
                await self.send_error(device_id, "Transcription failed")
                return
            
            self.logger.info(f"📝 Transcription: {text}")
            
            # STEP 2: SEND TRANSCRIPTION
            await self.send_message(device_id, {
                "type": "transcription",
                "text": text
            })

            # STEP 3: CHECK COMMANDS
            command = self.command_detector.detect(text)
            if command:
                await self._handle_command(device_id, command)
                return

            # STEP 4: STREAMING AI + TTS
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            sentence_count = 0
            total_audio_size = 0
            stream_start = time.time()
            
            async for original, cleaned, language, is_last in self.ai_service.chat_stream(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            ):
                if not cleaned:
                    if is_last:
                        await self.send_message(device_id, {
                            "type": "ai_response_end",
                            "total_chunks": sentence_count
                        })
                    continue
                
                sentence_count += 1
                
                self.logger.info(f"🔊 TTS #{sentence_count}: '{cleaned[:50]}...'")
                
                tts_start = time.time()
                audio_base64 = await self.tts_service.synthesize(cleaned, language)
                tts_time = time.time() - tts_start
                
                if not audio_base64:
                    self.logger.warning(f"⚠️ TTS failed for chunk {sentence_count}")
                    continue
                
                audio_size = len(audio_base64)
                total_audio_size += audio_size
                
                await self.send_message(device_id, {
                    "type": "ai_response_chunk",
                    "text": original,
                    "audio": audio_base64,
                    "audio_format": "mp3",
                    "language": language,
                    "chunk_index": sentence_count,
                    "chunk_size": audio_size,
                    "is_last": is_last,
                    "tts_time": round(tts_time, 2)
                })
                
                self.logger.info(
                    f"✅ Chunk {sentence_count}: {audio_size//1024}KB, {tts_time:.2f}s"
                )
            
            stream_time = time.time() - stream_start
            self.logger.info(
                f"🎉 Done! {sentence_count} chunks, "
                f"{total_audio_size//1024}KB, {stream_time:.2f}s"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Voice error: {e}", exc_info=True)
            await self.send_error(device_id, f"Error: {str(e)}")

    
    async def handle_ping(self, data: Dict):
        """Handle ping message"""
        device_id = data.get("device_id")
        await self.send_message(device_id, {"type": "pong"})
    
    async def handle_get_devices(self, data: Dict):
        """Handle get devices request"""
        try:
            device_id = data.get("device_id")
            devices = self.device_manager.get_all_devices()
            
            await self.send_message(device_id, {
                "type": "devices",
                "devices": devices
            })
            
        except Exception as e:
            self.logger.error(f"❌ Get devices error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Get devices error: {e}")
    
    async def handle_clear_history(self, data: Dict):
        """Handle clear history request"""
        try:
            device_id = data.get("device_id")
            self.ai_service.clear_history()
            
            await self.send_message(device_id, {
                "type": "history_cleared",
                "message": "Conversation history cleared"
            })
            
        except Exception as e:
            self.logger.error(f"❌ Clear history error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Clear history error: {e}")
    
    async def send_message(self, device_id: str, message: Dict):
        """Send message to device with connection check"""
        try:
            websocket = self.device_manager.get_connection(device_id)
            
            if not websocket:
                self.logger.warning(f"⚠️ No connection for device: {device_id}")
                return False
            
            if websocket.client_state.name != "CONNECTED":
                self.logger.warning(f"⚠️ WebSocket not connected for {device_id}")
                return False
            
            self.logger.info(f"📤 Sending '{message.get('type')}' to {device_id}")
            await websocket.send_text(json.dumps(message))
            return True
            
        except RuntimeError as e:
            if "close message" in str(e):
                self.logger.debug(f"WebSocket closed for {device_id}")
            else:
                self.logger.error(f"❌ Send error: {e}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Send error: {e}")
            return False

    async def send_error(self, device_id: str, error: str):
        """Send error message (SAFE - no cascade)"""
        try:
            websocket = self.device_manager.get_connection(device_id)
            
            if not websocket or websocket.client_state.name != "CONNECTED":
                return  # Silent fail
            
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": error
            }))
            
        except Exception:
            pass  # Silent fail, no logging to prevent cascade
    
    async def broadcast(self, message: Dict, exclude_device: Optional[str] = None):
        """Broadcast message to all connected devices"""
        devices = self.device_manager.get_all_connections()
        
        for device_id, websocket in devices.items():
            if device_id != exclude_device:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    self.logger.error(f"❌ Broadcast error to {device_id}: {e}")
