# File: app/ai_service.py
"""
AI Service - Handles chat with AI providers (OpenAI/DeepSeek/Azure)
✅ WITH AZURE OPENAI SUPPORT + Music function calling
"""

import os
import logging
import time
import re
import unicodedata
import json
from typing import List, Dict, Optional, AsyncGenerator, Any
from openai import AsyncOpenAI, AsyncAzureOpenAI  # ✅ ADD Azure client

# ... (keep MUSIC_FUNCTIONS exactly as is)

class AIService:
    """AI Chat Service with streaming support"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        system_prompt: str = "You are a helpful AI assistant.",
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_context: int = 10,
        provider: str = "openai",  # ✅ NEW: explicit provider
        azure_api_version: str = None  # ✅ NEW: for Azure
    ):
        """Initialize AI Service"""
        self.logger = logging.getLogger("AIService")

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_context = max_context
        self.provider = provider.lower()  # ✅ Use explicit provider
        self.azure_api_version = azure_api_version

        # ✅ Enable function calling (OpenAI and Azure only)
        self.use_function_calling = self.provider in ["openai", "azure"]

        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []

        self.logger.info("🤖 Initializing AI Service...")
        self.logger.info(f"   Provider: {self.provider}")
        self.logger.info(f"   Model: {model}")
        self.logger.info(f"   Streaming: Enabled")
        self.logger.info(f"   Function Calling: {'Enabled' if self.use_function_calling else 'Disabled'}")

        try:
            # ✅ Initialize appropriate client
            if self.provider == "azure":
                self.logger.info(f"   Azure Endpoint: {base_url}")
                self.logger.info(f"   Azure API Version: {azure_api_version}")
                
                self.client = AsyncAzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=base_url,
                    api_version=azure_api_version or "2024-02-15-preview"
                )
            else:
                # OpenAI or DeepSeek (OpenAI-compatible)
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            
            self.logger.info("✅ AI Service initialized")
            self._test_service()
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI client: {e}")
            raise

    # ✅ ADD: Music intent detection for DeepSeek
    def detect_music_intent(self, text: str) -> Optional[str]:
        """Detect music intent (for DeepSeek fallback)"""
        text_lower = text.lower()
        
        vi_patterns = [
            r'(?:mở|phát|chơi|bật|tìm|nghe)\s+(?:bài\s+)?(?:nhạc|hát|piano|guitar|music)',
            r'(?:cho|giúp)\s+(?:tôi|em|mình)\s+(?:nghe|mở|phát)\s+(?:nhạc|bài)',
            r'play\s+(?:music|song|piano|guitar)',
            r'tìm\s+(?:bài\s+)?(?:hát|nhạc)',
        ]
        
        for pattern in vi_patterns:
            match = re.search(pattern, text_lower)
            if match:
                after_command = text_lower[match.end():].strip()
                
                if after_command:
                    after_command = re.sub(r'^(về|của|bởi|by|from)\s+', '', after_command)
                    return after_command
                else:
                    return "piano music"
        
        return None

    # ... (keep clean_text_for_tts, detect_language, chat_stream exactly as they are)

    async def chat(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
        music_service=None
    ) -> Dict[str, Any]:
        """💬 CHAT WITH FUNCTION CALLING (OpenAI/Azure) OR KEYWORD DETECTION (DeepSeek)"""
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # ✅ STEP 1: Check for music intent (DeepSeek fallback)
            if not self.use_function_calling and music_service:
                music_query = self.detect_music_intent(user_message)
                
                if music_query:
                    self.logger.info(f"🎵 Music intent detected (keyword): '{music_query}'")
                    
                    music_results = await music_service.search_music(music_query, 1)
                    
                    if music_results:
                        first_result = music_results[0]
                        
                        response_text = (
                            f"🎵 Đang phát: {first_result['title']} "
                            f"của {first_result['channel']}"
                        )
                        
                        self.conversation_history.append({"role": "user", "content": user_message})
                        self.conversation_history.append({"role": "assistant", "content": response_text})
                        
                        cleaned_text = self.clean_text_for_tts(response_text)
                        language = self.detect_language(cleaned_text)
                        
                        return {
                            'response': response_text,
                            'cleaned_response': cleaned_text,
                            'language': language,
                            'function_call': {
                                'name': 'search_and_play_music',
                                'arguments': {'query': music_query, 'method': 'keyword'}
                            },
                            'music_result': first_result
                        }
            
            # ✅ STEP 2: Normal chat with function calling (OpenAI/Azure)
            self.conversation_history.append({"role": "user", "content": user_message})
            
            if len(self.conversation_history) > self.max_context * 2:
                self.conversation_history = self.conversation_history[-(self.max_context * 2):]
            
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history
            
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            # Add function calling if enabled
            if self.use_function_calling and music_service:
                request_params["tools"] = MUSIC_FUNCTIONS
                request_params["tool_choice"] = "auto"
                self.logger.info(f"🎵 Function calling enabled ({self.provider})")
            
            # Call API (works for all providers)
            response = await self.client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            
            # Handle function call
            if finish_reason == 'tool_calls' and message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                self.logger.info(f"🎯 Function call ({self.provider}): {function_name}({function_args})")
                
                if function_name == "search_and_play_music" and music_service:
                    query = function_args.get('query')
                    max_results = function_args.get('max_results', 1)
                    
                    music_results = await music_service.search_music(query, max_results)
                    
                    if music_results:
                        first_result = music_results[0]
                        
                        response_text = (
                            f"🎵 Đang phát: {first_result['title']} "
                            f"của {first_result['channel']}"
                        )
                        
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": response_text
                        })
                        
                        cleaned_text = self.clean_text_for_tts(response_text)
                        language = self.detect_language(cleaned_text)
                        
                        return {
                            'response': response_text,
                            'cleaned_response': cleaned_text,
                            'language': language,
                            'function_call': {
                                'name': function_name,
                                'arguments': function_args
                            },
                            'music_result': first_result
                        }
                    else:
                        response_text = f"❌ Xin lỗi, tôi không tìm thấy bài hát '{query}'."
                        
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": response_text
                        })
                        
                        cleaned_text = self.clean_text_for_tts(response_text)
                        language = self.detect_language(cleaned_text)
                        
                        return {
                            'response': response_text,
                            'cleaned_response': cleaned_text,
                            'language': language,
                            'function_call': None,
                            'music_result': None
                        }
            
            # Normal text response
            response_text = message.content or "Tôi không chắc cách trả lời câu hỏi đó."
            
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            cleaned_text = self.clean_text_for_tts(response_text)
            language = self.detect_language(cleaned_text)
            
            # Log to MySQL
            if conversation_logger and device_id:
                try:
                    await conversation_logger.log_conversation(
                        device_id=device_id,
                        device_type=device_type or "unknown",
                        user_message=user_message,
                        ai_response=response_text,
                        model=self.model,
                        provider=self.provider,
                        response_time=0.0,
                    )
                except Exception as log_error:
                    self.logger.error(f"❌ MySQL log error: {log_error}")
            
            return {
                'response': response_text,
                'cleaned_response': cleaned_text,
                'language': language,
                'function_call': None,
                'music_result': None
            }
        
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            
            error_text = "Xin lỗi, tôi gặp lỗi khi xử lý. Vui lòng thử lại."
            
            return {
                'response': error_text,
                'cleaned_response': error_text,
                'language': 'vi',
                'function_call': None,
                'music_result': None
            }

    def clear_history(self):
        """🗑️ Clear conversation history"""
        self.conversation_history = []
        self.logger.info("🗑️ Conversation history cleared")

    def get_history(self) -> List[Dict[str, str]]:
        """📜 Get conversation history"""
        return self.conversation_history.copy()

    def get_context_size(self) -> int:
        """📊 Get current context size"""
        return len(self.conversation_history)
