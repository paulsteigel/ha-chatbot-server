# File: app/websocket_handler.py
"""
WebSocket Handler - Handles WebSocket connections and messages
✅ UPDATED: All methods now support smart chunking for better TTS performance
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
        conversation_logger=None,
        music_service=None
    ):
        """Initialize WebSocket Handler"""
        self.logger = logging.getLogger('WebSocketHandler')
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.conversation_logger = conversation_logger
        self.music_service = music_service
        self.command_detector = CommandDetector()
        self.logger.info("🔌 WebSocket Handler initialized with smart chunking")
    
    async def handle_connection(self, websocket: WebSocket):
        """Handle WebSocket connection"""
        
        temp_id = f"temp-{id(websocket)}"
        device_id = None
        
        try:
            await websocket.accept()
            self.logger.info(f"📱 New WebSocket connection: {temp_id}")
            
            await self.device_manager.add_connection(temp_id, websocket)
            
            while True:
                try:
                    if websocket.client_state.name != "CONNECTED":
                        self.logger.warning(f"⚠️ WebSocket not connected: {temp_id}")
                        break
                    
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=300.0
                        )
                        
                        data_len = len(data)
                        self.logger.info(f"📦 Received {data_len} bytes from {temp_id if not device_id else device_id}")
                        
                        if data_len > 100000:
                            self.logger.warning(f"⚠️ Large message: {data_len / 1024:.1f} KB")
                            
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⏱️ Timeout waiting for message from {temp_id}")
                        await self.send_message(temp_id, {"type": "ping"})
                        continue
                    
                    try:
                        message = json.loads(data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"❌ JSON decode error: {e}")
                        self.logger.error(f"📝 First 500 chars: {data[:500]}")
                        await self.send_error(device_id or temp_id, "Invalid JSON format")
                        continue
                    
                    message_type = message.get('type', 'unknown')
                    
                    self.logger.info(f"📨 Message from {temp_id if not device_id else device_id}: {message_type}")
                    
                    if message_type == "register" and not device_id:
                        device_id_from_msg = message.get("device_id")
                        
                        if device_id_from_msg:
                            device_id = device_id_from_msg
                            
                            await self.device_manager.remove_connection(temp_id)
                            await self.device_manager.add_connection(device_id, websocket)
                            
                            self.logger.info(f"✅ Device registered: {device_id}")
                            
                            await self.handle_register(message)
                            continue
                    
                    current_id = device_id if device_id else temp_id
                    await self.route_message(current_id, message)
                    
                except WebSocketDisconnect:
                    self.logger.info(f"📱 WebSocket disconnected: {device_id or temp_id}")
                    break
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ JSON decode error: {e}")
                    await self.send_error(device_id or temp_id, "Invalid JSON format")
                    
                except Exception as e:
                    self.logger.error(f"❌ Message handling error: {e}", exc_info=True)
                    current_id = device_id if device_id else temp_id
                    if websocket.client_state.name == "CONNECTED":
                        await self.send_error(current_id, str(e))
                    else:
                        break
                        
        except RuntimeError as e:
            if "WebSocket is not connected" in str(e):
                self.logger.warning(f"⚠️ WebSocket connection failed for {device_id or temp_id}")
            else:
                self.logger.error(f"❌ Connection error: {e}", exc_info=True)
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}", exc_info=True)
            
        finally:
            final_id = device_id if device_id else temp_id
            await self.device_manager.remove_connection(final_id)
            self.logger.info(f"📱 Connection closed: {final_id}")
  
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

    # ═══════════════════════════════════════════════════════════════════
    # ✅ UPDATED: handle_chat() - NOW WITH CHUNK PROCESSING
    # ═══════════════════════════════════
    async def handle_chat_singthread(self, data: Dict):
        """Handle chat message from web interface with smart chunking"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Chat from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ─────────────────────────────────────────────────────────
            # STEP 1: GET AI RESPONSE (with chunks)
            # ─────────────────────────────────────────────────────────
            ai_response = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type,
                music_service=self.music_service
            )

            # ─────────────────────────────────────────────────────────
            # STEP 2: HANDLE MUSIC PLAYBACK (if found)
            # ─────────────────────────────────────────────────────────
            if ai_response.get('music_result'):
                music = ai_response['music_result']
                
                self.logger.info(f"🎵 Music found: {music['title']}")
                
                await self.send_message(device_id, {
                    "type": "play_music",
                    "title": music['title'],
                    "artist": music.get('channel', 'Unknown'),
                    "audio_url": music['audio_url'],
                    "duration": music.get('duration', 0),
                    "video_id": music['id']
                })

            # ─────────────────────────────────────────────────────────
            # STEP 3: PROCESS CHUNKS FOR TTS
            # ─────────────────────────────────────────────────────────
            response_text = ai_response['response']
            chunks = ai_response.get('chunks', [response_text])
            
            self.logger.info(f"📊 Processing {len(chunks)} chunks for TTS")
            
            for i, chunk_text in enumerate(chunks, 1):
                cleaned_chunk = self.ai_service.clean_text_for_tts(chunk_text)
                language = self.ai_service.detect_language(cleaned_chunk)
                
                # Synthesize each chunk
                audio_bytes, provider = await self.tts_service.synthesize_chunk(
                    chunk_text, cleaned_chunk, language
                )
                
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    
                    # Send chunk to client
                    await self.send_message(device_id, {
                        "type": "audio_chunk",
                        "audio": audio_base64,
                        "text": chunk_text,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "is_final": (i == len(chunks)),
                        "format": "wav",
                        "language": language,
                        "tts_provider": provider
                    })
                    
                    self.logger.info(
                        f"📤 Sent chunk {i}/{len(chunks)}: {len(audio_bytes)} bytes "
                        f"({provider}) - '{chunk_text[:40]}...'"
                    )
            
            # ─────────────────────────────────────────────────────────
            # STEP 4: SEND COMPLETION MESSAGE
            # ─────────────────────────────────────────────────────────
            await self.send_message(device_id, {
                "type": "chat_response_complete",
                "full_text": response_text,
                "total_chunks": len(chunks)
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat error: {e}")
    
    async def handle_chat(self, data: Dict):
        """Handle chat with STREAMING + TTS BATCHING"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Chat from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ─────────────────────────────────────────────────────────
            # ✅ STREAMING + BATCHING
            # ─────────────────────────────────────────────────────────
            full_response = ""
            batch_count = 0
            music_sent = False
            
            # Batch settings
            accumulated_text = ""
            accumulated_chunks = []
            BATCH_SIZE = 2  # Accumulate 2 chunks before TTS
            MIN_CHARS_FOR_TTS = 150  # Or at least 150 chars
            
            async for original, cleaned, language, is_last, music_result in self.ai_service.chat_stream(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type,
                music_service=self.music_service
            ):
                # ─────────────────────────────────────────────────────
                # Handle music
                # ─────────────────────────────────────────────────────
                if music_result and not music_sent:
                    self.logger.info(f"🎵 Sending music: {music_result['title']}")
                    await self.send_message(device_id, {
                        "type": "play_music",
                        "title": music_result['title'],
                        "artist": music_result.get('channel', 'Unknown'),
                        "audio_url": music_result['audio_url'],
                        "duration": music_result.get('duration', 0),
                        "video_id": music_result['id']
                    })
                    music_sent = True
                
                # Skip empty chunks
                if not original.strip():
                    if is_last:
                        break
                    continue
                
                full_response += original + " "
                
                # ─────────────────────────────────────────────────────
                # ✅ ACCUMULATE CHUNKS
                # ─────────────────────────────────────────────────────
                accumulated_text += original + " "
                accumulated_chunks.append(original)
                
                # ─────────────────────────────────────────────────────
                # ✅ DECIDE WHEN TO TTS
                # ─────────────────────────────────────────────────────
                should_tts = (
                    len(accumulated_chunks) >= BATCH_SIZE or
                    len(accumulated_text) >= MIN_CHARS_FOR_TTS or
                    is_last
                )
                
                if should_tts and accumulated_text.strip():
                    batch_count += 1
                    
                    try:
                        self.logger.info(
                            f"🔊 TTS batch {batch_count}: {len(accumulated_chunks)} chunks, "
                            f"{len(accumulated_text)} chars"
                        )
                        
                        # ✅ TTS THE BATCH
                        cleaned_batch = self.ai_service.clean_text_for_tts(accumulated_text)
                        batch_language = self.ai_service.detect_language(cleaned_batch)
                        
                        audio_bytes, provider = await self.tts_service.synthesize_chunk(
                            original_text=accumulated_text.strip(),
                            cleaned_text=cleaned_batch,
                            language=batch_language
                        )
                        
                        if audio_bytes:
                            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                            
                            # Send batch
                            await self.send_message(device_id, {
                                "type": "audio_chunk",
                                "audio": audio_base64,
                                "text": accumulated_text.strip(),
                                "chunk": batch_count,
                                "is_final": is_last,
                                "format": "wav",
                                "language": batch_language,
                                "tts_provider": provider
                            })
                            
                            self.logger.info(
                                f"📤 Sent batch {batch_count}: {len(audio_bytes)} bytes "
                                f"({provider}) - '{accumulated_text[:40]}...'"
                            )
                        
                        # ✅ RESET ACCUMULATOR
                        accumulated_text = ""
                        accumulated_chunks = []
                    
                    except Exception as batch_error:
                        self.logger.error(f"❌ Batch {batch_count} failed: {batch_error}")
                        accumulated_text = ""
                        accumulated_chunks = []
                        continue
            
            # ─────────────────────────────────────────────────────────
            # Send completion
            # ─────────────────────────────────────────────────────────
            self.logger.info(f"✅ Chat complete: {batch_count} batches")
            
            await self.send_message(device_id, {
                "type": "chat_response_complete",
                "full_text": full_response.strip(),
                "total_chunks": batch_count
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # ✅ UPDATED: handle_text() - NOW WITH CHUNK PROCESSING
    # ═══════════════════════════════════════════════════════════════════
    async def handle_text_singlethread(self, data: Dict):
        """Handle text message from ESP32 with smart chunking"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Text from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ─────────────────────────────────────────────────────────
            # STEP 1: GET AI RESPONSE (with chunks)
            # ─────────────────────────────────────────────────────────
            ai_response = await self.ai_service.chat(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type,
                music_service=self.music_service
            )

            # ─────────────────────────────────────────────────────────
            # STEP 2: HANDLE MUSIC PLAYBACK (if found)
            # ─────────────────────────────────────────────────────────
            if ai_response.get('music_result'):
                music = ai_response['music_result']
                
                self.logger.info(f"🎵 Music found: {music['title']}")
                
                await self.send_message(device_id, {
                    "type": "play_music",
                    "title": music['title'],
                    "artist": music.get('channel', 'Unknown'),
                    "audio_url": music['audio_url'],
                    "duration": music.get('duration', 0),
                    "video_id": music['id']
                })

            # ─────────────────────────────────────────────────────────
            # STEP 3: SEND TEXT RESPONSE FIRST
            # ─────────────────────────────────────────────────────────
            response_text = ai_response['response']
            language = ai_response['language']

            await self.send_message(device_id, {
                "type": "text",
                "text": response_text,
                "language": language
            })

            # ─────────────────────────────────────────────────────────
            # STEP 4: PROCESS CHUNKS FOR TTS
            # ─────────────────────────────────────────────────────────
            chunks = ai_response.get('chunks', [response_text])
            
            self.logger.info(f"📊 Processing {len(chunks)} chunks for TTS")
            
            for i, chunk_text in enumerate(chunks, 1):
                cleaned_chunk = self.ai_service.clean_text_for_tts(chunk_text)
                chunk_language = self.ai_service.detect_language(cleaned_chunk)
                
                # Synthesize each chunk
                audio_bytes, provider = await self.tts_service.synthesize_chunk(
                    chunk_text, cleaned_chunk, chunk_language
                )
                
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    
                    # Send audio chunk
                    await self.send_message(device_id, {
                        "type": "audio",
                        "audio": audio_base64,
                        "format": "wav",
                        "language": chunk_language,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "is_final": (i == len(chunks)),
                        "tts_provider": provider
                    })
                    
                    self.logger.info(
                        f"📤 Sent audio chunk {i}/{len(chunks)}: {len(audio_bytes)} bytes "
                        f"({provider}) - '{chunk_text[:40]}...'"
                    )
            
        except Exception as e:
            self.logger.error(f"❌ Text error: {e}", exc_info=True)
            await self.send_error(device_id, f"Text error: {e}")
    
    async def handle_text(self, data: Dict):
        """Handle text with STREAMING + TTS BATCHING"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Text from {device_id}: {text}")
            
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            # ─────────────────────────────────────────────────────────
            # ✅ STREAMING + BATCHING
            # ─────────────────────────────────────────────────────────
            full_response = ""
            batch_count = 0
            music_sent = False
            text_sent = False
            
            # Batch settings
            accumulated_text = ""
            accumulated_chunks = []
            BATCH_SIZE = 2
            MIN_CHARS_FOR_TTS = 150
            
            async for original, cleaned, language, is_last, music_result in self.ai_service.chat_stream(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type,
                music_service=self.music_service
            ):
                # ─────────────────────────────────────────────────────
                # Handle music
                # ─────────────────────────────────────────────────────
                if music_result and not music_sent:
                    self.logger.info(f"🎵 Sending music: {music_result['title']}")
                    await self.send_message(device_id, {
                        "type": "play_music",
                        "title": music_result['title'],
                        "artist": music_result.get('channel', 'Unknown'),
                        "audio_url": music_result['audio_url'],
                        "duration": music_result.get('duration', 0),
                        "video_id": music_result['id']
                    })
                    music_sent = True
                
                # Skip empty chunks
                if not original.strip():
                    if is_last:
                        break
                    continue
                
                full_response += original + " "
                
                # ─────────────────────────────────────────────────────
                # ✅ Send text preview on first chunk (ESP32 specific)
                # ─────────────────────────────────────────────────────
                if not text_sent:
                    await self.send_message(device_id, {
                        "type": "text",
                        "text": original,
                        "language": language
                    })
                    text_sent = True
                
                # ─────────────────────────────────────────────────────
                # ✅ ACCUMULATE CHUNKS
                # ─────────────────────────────────────────────────────
                accumulated_text += original + " "
                accumulated_chunks.append(original)
                
                # ─────────────────────────────────────────────────────
                # ✅ DECIDE WHEN TO TTS
                # ─────────────────────────────────────────────────────
                should_tts = (
                    len(accumulated_chunks) >= BATCH_SIZE or
                    len(accumulated_text) >= MIN_CHARS_FOR_TTS or
                    is_last
                )
                
                if should_tts and accumulated_text.strip():
                    batch_count += 1
                    
                    try:
                        self.logger.info(
                            f"🔊 TTS batch {batch_count}: {len(accumulated_chunks)} chunks, "
                            f"{len(accumulated_text)} chars"
                        )
                        
                        # ✅ TTS THE BATCH
                        cleaned_batch = self.ai_service.clean_text_for_tts(accumulated_text)
                        batch_language = self.ai_service.detect_language(cleaned_batch)
                        
                        audio_bytes, provider = await self.tts_service.synthesize_chunk(
                            original_text=accumulated_text.strip(),
                            cleaned_text=cleaned_batch,
                            language=batch_language
                        )
                        
                        if audio_bytes:
                            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                            
                            # Send batch (ESP32 format)
                            await self.send_message(device_id, {
                                "type": "audio",
                                "audio": audio_base64,
                                "format": "wav",
                                "language": batch_language,
                                "chunk": batch_count,
                                "is_final": is_last,
                                "tts_provider": provider
                            })
                            
                            self.logger.info(
                                f"📤 Sent audio batch {batch_count}: {len(audio_bytes)} bytes "
                                f"({provider}) - '{accumulated_text[:40]}...'"
                            )
                        
                        # ✅ RESET ACCUMULATOR
                        accumulated_text = ""
                        accumulated_chunks = []
                    
                    except Exception as batch_error:
                        self.logger.error(f"❌ Batch {batch_count} failed: {batch_error}")
                        accumulated_text = ""
                        accumulated_chunks = []
                        continue
            
            # ─────────────────────────────────────────────────────────
            # Done
            # ─────────────────────────────────────────────────────────
            self.logger.info(f"✅ Text complete: {batch_count} batches")
            
        except Exception as e:
            self.logger.error(f"❌ Text error: {e}", exc_info=True)
            await self.send_error(device_id, f"Text error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # ✅ KEEP: handle_voice() - Already uses streaming with smart splitting
    # ═══════════════════════════════════════════════════════════════════
    async def handle_voice(self, data: Dict):
        """Handle voice message with streaming response + music support"""
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
            # STEP 1: TRANSCRIBE
            # ─────────────────────────────────────────────────────────
            audio_data = base64.b64decode(audio_base64)
            text = await self.stt_service.transcribe(audio_data, stt_language)
            
            if not text:
                await self.send_error(device_id, "Could not transcribe audio")
                return
            
            self.logger.info(f"📝 Transcription: {text}")
            
            # ─────────────────────────────────────────────────────────
            # STEP 2: SEND TRANSCRIPTION
            # ─────────────────────────────────────────────────────────
            self.logger.info(f"📨 Sending transcription to frontend...")
            await self.send_message(device_id, {
                "type": "transcription",
                "text": text
            })

            # ─────────────────────────────────────────────────────────
            # STEP 3: CHECK FOR COMMANDS
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
                return

            # ─────────────────────────────────────────────────────────
            # STEP 4: GET AI STREAMING RESPONSE WITH MUSIC SUPPORT
            # ─────────────────────────────────────────────────────────
            device_info = self.device_manager.devices.get(device_id, {})
            device_type = device_info.get('type', 'unknown')
            
            full_original_text = ""
            sentence_count = 0
            music_sent = False
            
            # ✅ Stream with smart splitting (already implemented in ai_service)
            async for original, cleaned, language, is_last, music_result in self.ai_service.chat_stream(
                user_message=text,
                conversation_logger=self.conversation_logger,
                device_id=device_id,
                device_type=device_type,
                music_service=self.music_service
            ):
                # ─────────────────────────────────────────────────────
                # STEP 5: HANDLE MUSIC PLAYBACK (if found)
                # ─────────────────────────────────────────────────────
                if music_result and not music_sent:
                    self.logger.info(f"🎵 Sending music to device: {music_result['title']}")
                    
                    await self.send_message(device_id, {
                        "type": "play_music",
                        "title": music_result['title'],
                        "artist": music_result.get('channel', 'Unknown'),
                        "audio_url": music_result['audio_url'],
                        "duration": music_result.get('duration', 0),
                        "video_id": music_result['id']
                    })
                    
                    music_sent = True
                
                # Skip empty chunks
                if not original.strip():
                    if is_last:
                        break
                    continue
                
                sentence_count += 1
                full_original_text += original + " "
                
                # ─────────────────────────────────────────────────────
                # STEP 6: SYNTHESIZE CHUNK WITH FALLBACK
                # ─────────────────────────────────────────────────────
                try:
                    wav_bytes, tts_provider = await self.tts_service.synthesize_chunk(
                        original_text=original,
                        cleaned_text=cleaned,
                        language=language
                    )
                    
                    audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
                    
                    # ─────────────────────────────────────────────────
                    # STEP 7: SEND AUDIO CHUNK
                    # ─────────────────────────────────────────────────
                    await self.send_message(device_id, {
                        "type": "audio_chunk",
                        "chunk_index": sentence_count - 1,
                        "chunk_text": original,
                        "audio": audio_base64,
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
                    continue
            
            # ─────────────────────────────────────────────────────────
            # STEP 8: LOG CONVERSATION TO MYSQL
            # ─────────────────────────────────────────────────────────
            if self.conversation_logger and full_original_text.strip():
                try:
                    await self.conversation_logger.log_conversation(
                        device_id=device_id,
                        device_type=device_type,
                        user_message=text,
                        ai_response=full_original_text.strip(),
                        model=self.ai_service.model,
                        provider=self.ai_service.provider,
                        response_time=0.0,
                    )
                    self.logger.info(f"💾 Conversation saved: {device_id}")
                except Exception as log_error:
                    self.logger.error(f"❌ MySQL log error: {log_error}")
            
            # ─────────────────────────────────────────────────────────
            # STEP 9: SEND COMPLETION MESSAGE
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
    # UTILITY METHODS - Keep unchanged
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
