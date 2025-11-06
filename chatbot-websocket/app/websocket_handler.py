# File: app/websocket_handler.py
"""
WebSocket Handler - Handles WebSocket connections and messages
✅ UPDATED: handle_voice() now uses streaming chunks
"""

import logging
import json
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
        # ← KEEP: All initialization stays the same
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
        # ← KEEP: This entire method stays exactly the same
        try:
            await websocket.accept()
            self.logger.info(f"📱 New WebSocket connection: {device_id}")
            
            await self.device_manager.add_connection(device_id, websocket)
            
            while True:
                try:
                    if websocket.client_state.name != "CONNECTED":
                        self.logger.warning(f"⚠️ WebSocket not connected: {device_id}")
                        break
                    
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=300.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⏱️ Timeout waiting for message from {device_id}")
                        await self.send_message(device_id, {"type": "ping"})
                        continue
                    
                    message = json.loads(data)
                    
                    self.logger.info(f"📨 Message from {device_id}: {message.get('type', 'unknown')}")
                    
                    await self.route_message(device_id, message)
                    
                except WebSocketDisconnect:
                    self.logger.info(f"📱 WebSocket disconnected: {device_id}")
                    break
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ JSON decode error: {e}")
                    await self.send_error(device_id, "Invalid JSON format")
                    
                except Exception as e:
                    self.logger.error(f"❌ Message handling error: {e}", exc_info=True)
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
            await self.device_manager.remove_connection(device_id)
            self.logger.info(f"📱 Connection closed: {device_id}")
  
    async def route_message(self, device_id: str, message: Dict):
        """Route message to appropriate handler"""
        # ← KEEP: This stays exactly the same
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
    
    # ═══════════════════════════════════════════════════════════════════
    # ← KEEP: These methods stay exactly the same
    # ═══════════════════════════════════════════════════════════════════
    async def handle_register(self, data: Dict):
        """Handle device registration"""
        try:
            device_id = data.get("device_id")
            device_type = data.get("device_type", "unknown")
            firmware_version = data.get("firmware_version", "unknown")
            
            self.logger.info(f"✅ Registering device: {device_id}")
            self.logger.info(f"   Type: {device_type}")
            self.logger.info(f"   Firmware: {firmware_version}")
            
            await self.device_manager.register_device(
                device_id=device_id,
                device_type=device_type,
                firmware_version=firmware_version
            )
            
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
        # ← KEEP: This stays exactly the same
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Chat from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            original_text, cleaned_text, language = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            )

            if not original_text:
                await self.send_error(device_id, "AI service error")
                return

            audio_base64 = await self.tts_service.synthesize(cleaned_text, language)

            await self.send_message(device_id, {
                "type": "chat_response",
                "text": original_text,
                "audio": audio_base64,
                "audio_format": "wav",  # ← Changed from mp3
                "language": language
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat error: {e}")
    
    async def handle_text(self, data: Dict):
        """Handle text message from ESP32"""
        # ← KEEP: This stays exactly the same
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Text from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            original_text, cleaned_text, language = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            )

            if not original_text:
                await self.send_error(device_id, "AI service error")
                return

            await self.send_message(device_id, {
                "type": "text",
                "text": original_text,
                "language": language
            })

            audio_base64 = await self.tts_service.synthesize(cleaned_text, language)

            if audio_base64:
                await self.send_message(device_id, {
                    "type": "audio",
                    "audio": audio_base64,
                    "format": "wav",  # ← Changed from mp3
                    "language": language
                })
            
        except Exception as e:
            self.logger.error(f"❌ Text error: {e}", exc_info=True)
            await self.send_error(device_id, f"Text error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # ← MODIFIED: handle_voice() - NEW STREAMING IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════
    async def handle_voice(self, data: Dict):
        """Handle voice message with streaming response"""
        try:
            device_id = data.get("device_id")
            audio_base64 = data.get("audio")
            audio_format = data.get("format", "webm")
            stt_language = data.get("language", "vi")
            
            if not audio_base64:
                await self.send_error(device_id, "Missing audio data")
                return
            
            self.logger.info(
                f"🎤 Voice from {device_id} "
                f"(format: {audio_format}, STT language: {stt_language})"
            )
            
            # ─────────────────────────────────────────────────────────
            # STEP 1: TRANSCRIBE (← KEEP)
            # ─────────────────────────────────────────────────────────
            audio_data = base64.b64decode(audio_base64)
            text = await self.stt_service.transcribe(audio_data, stt_language)
            
            if not text:
                await self.send_error(device_id, "Could not transcribe audio")
                return
            
            self.logger.info(f"📝 Transcription: {text}")
            
            # ─────────────────────────────────────────────────────────
            # STEP 2: SEND TRANSCRIPTION (← KEEP)
            # ─────────────────────────────────────────────────────────
            self.logger.info(f"📨 Sending transcription to frontend...")
            await self.send_message(device_id, {
                "type": "transcription",
                "text": text
            })

            # ─────────────────────────────────────────────────────────
            # STEP 3: CHECK FOR COMMANDS (← KEEP)
            # ─────────────────────────────────────────────────────────
            command = self.command_detector.detect(text)

            if command:
                self.logger.info(
                    f"🎯 Command detected: {command['command']} -> {command['action']}"
                )
                
                await self.send_message(device_id, {
                    "type": "command",
                    "command": command["command"],
                    "action": command["action"],
                    "value": command["value"]
                })
                
                quick_responses = {
                    "volume_up": "Đã tăng âm lượng! 🔊",
                    "volume_down": "Đã giảm âm lượng! 🔉",
                    "light_on": "Đã bật đèn! 💡",
                    "light_off": "Đã tắt đèn! 🌙",
                    "stop": "Dừng lại! 🛑",
                    "continue": "Tiếp tục! ▶️",
                    "fan_on": "Đã bật quạt! 🌀",
                    "fan_off": "Đã tắt quạt! ⭕",
                }
                
                response_text = quick_responses.get(
                    command["command"], 
                    "Đã thực hiện!"
                )
                
                await self.send_message(device_id, {
                    "type": "command_response",
                    "text": response_text
                })
                
                self.logger.info(f"✅ Command executed: {response_text}")
                return  # ← STOP HERE!

            # ─────────────────────────────────────────────────────────
            # STEP 4: GET AI STREAMING RESPONSE (← NEW!)
            # ─────────────────────────────────────────────────────────
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # Collect all sentences for display
            full_original_text = ""
            sentence_count = 0
            
            # Stream AI response sentence by sentence
            async for original, cleaned, language, is_last in self.ai_service.chat_stream(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type
            ):
                # Skip empty chunks
                if not original.strip():
                    if is_last:
                        # End of stream
                        break
                    continue
                
                sentence_count += 1
                full_original_text += original + " "
                
                # ─────────────────────────────────────────────────────
                # STEP 5: SYNTHESIZE CHUNK WITH FALLBACK (← NEW!)
                # ─────────────────────────────────────────────────────
                try:
                    wav_bytes, tts_provider = await self.tts_service.synthesize_chunk(
                        original_text=original,   # ← For OpenAI fallback (with emoji)
                        cleaned_text=cleaned,     # ← For Piper (no emoji)
                        language=language
                    )
                    
                    # Convert to base64
                    audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
                    
                    # ─────────────────────────────────────────────────
                    # STEP 6: SEND AUDIO CHUNK (← NEW!)
                    # ─────────────────────────────────────────────────
                    await self.send_message(device_id, {
                        "type": "audio_chunk",
                        "chunk_index": sentence_count - 1,
                        "chunk_text": original,      # Display text (with emoji)
                        "audio": audio_base64,       # WAV 16kHz base64
                        "format": "wav",
                        "sample_rate": 16000,
                        "tts_provider": tts_provider,
                        "language": language,
                        "is_last": is_last
                    })
                    
                    self.logger.info(
                        f"📤 Sent chunk {sentence_count}: "
                        f"{len(wav_bytes)} bytes WAV ({tts_provider}) - "
                        f"'{original[:40]}{'...' if len(original) > 40 else ''}'"
                    )
                    
                except Exception as chunk_error:
                    self.logger.error(
                        f"❌ Failed to synthesize chunk {sentence_count}: {chunk_error}"
                    )
                    # Continue with next chunk instead of failing completely
                    continue
            
            # ─────────────────────────────────────────────────────────
            # STEP 7: LOG CONVERSATION TO MYSQL (← ADD THIS!)
            # ─────────────────────────────────────────────────────────
            if self.conversation_logger and full_original_text.strip():
                try:
                    import time
                    await self.conversation_logger.log_conversation(
                        device_id=device_id,
                        device_type=device_type,
                        user_message=text,  # ← User's voice transcription
                        ai_response=full_original_text.strip(),  # ← Full AI response
                        model=self.ai_service.model,
                        provider=self.ai_service.provider,
                        response_time=0.0,  # ← We don't track time in streaming
                    )
                    self.logger.info(f"💾 Conversation saved: {device_id}")
                except Exception as log_error:
                    self.logger.error(f"❌ MySQL log error: {log_error}")
                    
            # ─────────────────────────────────────────────────────────
            # STEP 8: SEND COMPLETION MESSAGE (← NEW!)
            # ─────────────────────────────────────────────────────────
            self.logger.info(
                f"✅ Voice response complete: {sentence_count} chunks, "
                f"{len(full_original_text)} chars"
            )
            
            await self.send_message(device_id, {
                "type": "ai_response_complete",
                "total_chunks": sentence_count,
                "full_text": full_original_text.strip()
            })
            
        except Exception as e:
            self.logger.error(f"❌ Voice error: {e}", exc_info=True)
            await self.send_error(device_id, f"Voice error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # ← KEEP: These methods stay exactly the same
    # ═══════════════════════════════════════════════════════════════════
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
            
            self.logger.debug(f"📤 Sending '{message.get('type')}' to {device_id}")
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
                return
            
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": error
            }))
            
        except Exception:
            pass
    
    async def broadcast(self, message: Dict, exclude_device: Optional[str] = None):
        """Broadcast message to all connected devices"""
        devices = self.device_manager.get_all_connections()
        
        for device_id, websocket in devices.items():
            if device_id != exclude_device:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    self.logger.error(f"❌ Broadcast error to {device_id}: {e}")
