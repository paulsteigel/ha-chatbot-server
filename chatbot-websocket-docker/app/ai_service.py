# File: app/ai_service.py
"""
AI Service - Handles chat with AI providers (OpenAI/DeepSeek/Azure)
✅ Streaming support with sentence-level chunking + SMART SPLITTING
✅ Enhanced emoji/markdown removal for TTS
✅ Azure OpenAI support
✅ Music function calling (OpenAI/Azure) + keyword detection (DeepSeek)
"""

import os
import logging
import time
import re
import unicodedata
import json
from typing import List, Dict, Optional, AsyncGenerator, Any
from openai import AsyncOpenAI, AsyncAzureOpenAI


# ═══════════════════════════════════════════════════════════════════
# MUSIC FUNCTION DEFINITION
# ═══════════════════════════════════════════════════════════════════
MUSIC_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_and_play_music",
            "description": "Search for music on YouTube and play it. Use when user asks to play a song, music, or audio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The song name, artist, or search query. Examples: 'the tempest piano', 'beethoven symphony 5', 'lofi hip hop'"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 1 for immediate playback, 5 for showing options)",
                        "default": 1
                    }
                },
                "required": ["query"]
            }
        }
    }
]


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
        provider: str = "openai",
        azure_api_version: str = None
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
        self.provider = provider.lower()
        self.azure_api_version = azure_api_version

        # ✅ Enable function calling (OpenAI and Azure only)
        self.use_function_calling = self.provider in ["openai", "azure"]

        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []

        self.logger.info("🤖 Initializing AI Service...")
        self.logger.info(f"   Provider: {self.provider}")
        self.logger.info(f"   Model: {model}")
        self.logger.info(f"   Streaming: Enabled with smart splitting")  # ✅ UPDATED
        self.logger.info(f"   Function Calling: {'Enabled' if self.use_function_calling else 'Disabled'}")
        self.logger.info(f"   Emoji removal: Enhanced")

        try:
            if self.provider == "azure":
                self.logger.info(f"   Azure Endpoint: {base_url}")
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
                self.logger.info("✅ Using AsyncOpenAI (Azure Foundry)")
            else:
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            
            self.logger.info("✅ AI Service initialized")
            self._test_service()
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI client: {e}")
            raise

    def _test_service(self):
        """Test AI service"""
        import asyncio

        async def test():
            result = await self.chat("Hello")
            if isinstance(result, dict):
                self.logger.info(f"✅ Test response: {result.get('response', '')[:50]}...")
            self.clear_history()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(test())
            else:
                asyncio.run(test())
            self.logger.info("✅ AI test successful")
        except Exception as e:
            self.logger.warning(f"⚠️ AI test skipped: {e}")

    def detect_music_intent(self, text: str) -> Optional[str]:
        """🎵 DETECT MUSIC INTENT (for DeepSeek fallback)"""
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

    def clean_text_for_tts(self, text: str) -> str:
        """✨ CLEAN TEXT FOR TTS - ENHANCED VERSION ✨"""
        if not text:
            return ""
        
        original_text = text
        cleaned = text
        
        # STEP 1: Remove ALL emoji
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"
            "\U0001F300-\U0001F5FF"
            "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002700-\U000027BF"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2600-\u26FF"
            "\u2700-\u27BF"
            "\uFE00-\uFE0F"
            "\u203C-\u3299"
            "\u200D"
            "\u2300-\u23FF"
            "\u2B50-\u2BFF"
            "]+",
            flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub('', cleaned)
        
        # STEP 2: Fallback - Remove using Unicode categories
        def is_emoji_char(c):
            cat = unicodedata.category(c)
            return cat in ['So', 'Cn']
        
        cleaned = ''.join(c for c in cleaned if not is_emoji_char(c))
        
        # STEP 3: Remove Markdown
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)
        cleaned = re.sub(r'__(.+?)__', r'\1', cleaned)
        cleaned = re.sub(r'_(.+?)_', r'\1', cleaned)
        cleaned = re.sub(r'~~(.+?)~~', r'\1', cleaned)
        cleaned = re.sub(r'`{1,3}(.+?)`{1,3}', r'\1', cleaned)
        cleaned = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', cleaned)
        
        # STEP 4: Remove brackets
        cleaned = re.sub(r'\[\w\]', '', cleaned)
        cleaned = re.sub(r'\[!\]', '', cleaned)
        
        # STEP 5: Remove extra symbols
        vietnamese_chars = (
            'àáảãạăằắẳẵặâầấẩẫậ'
            'èéẻẽẹêềếểễệ'
            'ìíỉĩị'
            'òóỏõọôồốổỗộơờớởỡợ'
            'ùúủũụưừứửữự'
            'ỳýỷỹỵ'
            'đĐ'
        )
        
        allowed_pattern = rf'[^\w\s\.,!?;:\-\'\"/()\[\]{vietnamese_chars}]'
        cleaned = re.sub(allowed_pattern, '', cleaned)
        
        # STEP 6: Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        cleaned = re.sub(r'\s+([.,!?;:])', r'\1', cleaned)
        
        return cleaned.strip()

    def detect_language(self, text: str) -> str:
        """🔍 DETECT LANGUAGE - Vietnamese priority"""
        vietnamese_pattern = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]'
        
        if re.search(vietnamese_pattern, text):
            return "vi"
        
        ascii_letters = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.sub(r'[\s\d\W]', '', text))
        
        if total_chars > 0 and ascii_letters / total_chars > 0.7:
            return "en"
        
        return "vi"

    # ✅ NEW: HELPER METHOD FOR SPLITTING LONG RESPONSES
    def split_long_response(self, text: str, max_chunk_size: int = 150) -> List[str]:
        """
        ✂️ SPLIT LONG RESPONSE INTO CHUNKS
        
        Splits at:
        1. Sentence endings (. ! ?)
        2. Commas/semicolons (if > 120 chars)
        3. Force split (if > max_chunk_size)
        
        Returns list of chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        current = ""
        
        # Split by sentences first
        sentences = re.split(r'([.!?。！？]\s+)', text)
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
            
            full_sentence = sentence + delimiter
            
            # If adding this sentence exceeds limit
            if len(current) + len(full_sentence) > max_chunk_size:
                # Yield current if not empty
                if current:
                    chunks.append(current.strip())
                    current = ""
                
                # If sentence itself is too long, split it
                if len(full_sentence) > max_chunk_size:
                    # Try split at comma
                    parts = re.split(r'([,;，；]\s+)', full_sentence)
                    
                    for j in range(0, len(parts), 2):
                        part = parts[j]
                        part_delim = parts[j + 1] if j + 1 < len(parts) else ""
                        full_part = part + part_delim
                        
                        if len(current) + len(full_part) > max_chunk_size:
                            if current:
                                chunks.append(current.strip())
                            current = full_part
                        else:
                            current += full_part
                else:
                    current = full_sentence
            else:
                current += full_sentence
        
        # Add remaining
        if current:
            chunks.append(current.strip())
        
        return chunks

    async def chat_stream(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
        music_service=None
    ) -> AsyncGenerator[tuple[str, str, str, bool, Optional[dict]], None]:
        """🌊 STREAM CHAT RESPONSE - WITH MUSIC SUPPORT (2-STEP APPROACH)"""
        start_time = time.time()
        
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # ═══════════════════════════════════════════════════════════
            # ✅ STEP 1: CHECK FOR MUSIC INTENT FIRST (NON-STREAMING)
            # ═══════════════════════════════════════════════════════════
            if music_service:
                # Try function calling first (OpenAI/Azure)
                if self.use_function_calling:
                    self.logger.info(f"🎵 Checking for function calls ({self.provider})...")
                    
                    # ✅ Use non-streaming chat() to detect function calls
                    result = await self.chat(
                        user_message=user_message,
                        conversation_logger=conversation_logger,
                        device_id=device_id,
                        device_type=device_type,
                        music_service=music_service
                    )
                    
                    # If music was found, yield it and return
                    if result.get('music_result'):
                        self.logger.info(f"🎵 Music function called successfully!")
                        
                        yield (
                            result['response'],
                            result['cleaned_response'],
                            result['language'],
                            True,  # is_final
                            result['music_result']  # ✅ Music data
                        )
                        return
                
                # Fallback: Keyword detection (DeepSeek)
                else:
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
                            
                            yield (
                                response_text,
                                cleaned_text,
                                language,
                                True,
                                first_result  # ✅ Music data
                            )
                            return
            
            # ═══════════════════════════════════════════════════════════
            # ✅ STEP 2: NORMAL STREAMING CHAT (No music detected)
            # ═══════════════════════════════════════════════════════════
            self.conversation_history.append({"role": "user", "content": user_message})
            
            if len(self.conversation_history) > self.max_context * 2:
                self.conversation_history = self.conversation_history[-(self.max_context * 2):]
            
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history
            
            request_start = time.time()
            self.logger.info(f"⏱️  Streaming from {self.provider.upper()}...")
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            
            full_response = ""
            current_sentence = ""
            first_token_time = None
            sentence_count = 0
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_response += token
                        current_sentence += token
                    
                    if first_token_time is None:
                        first_token_time = time.time() - request_start
                        self.logger.info(f"⚡ First token: {first_token_time:.2f}s")
                    
                    # Sentence detection
                    if re.search(r'[.!?。！？]\s*$', current_sentence):
                        original = current_sentence.strip()
                        
                        if original:
                            sentence_count += 1
                            cleaned = self.clean_text_for_tts(original)
                            
                            if cleaned:
                                language = self.detect_language(cleaned)
                                
                                self.logger.info(
                                    f"📤 Chunk {sentence_count} ({language}, sentence_end, {len(original)} chars): "
                                    f"'{original[:40]}...'"
                                )
                                
                                yield (original, cleaned, language, False, None)
                            
                            current_sentence = ""
            
            # Final sentence
            if current_sentence.strip():
                original = current_sentence.strip()
                cleaned = self.clean_text_for_tts(original)
                
                if cleaned:
                    sentence_count += 1
                    language = self.detect_language(cleaned)
                    self.logger.info(f"📤 Final chunk {sentence_count} ({len(original)} chars)")
                    yield (original, cleaned, language, True, None)
                else:
                    yield ("", "", "", True, None)
            else:
                yield ("", "", "", True, None)
            
            # Save to history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
            
            request_time = time.time() - request_start
            
            self.logger.info(
                f"🤖 Complete: {len(full_response)} chars, {sentence_count} chunks"
            )
            self.logger.info(
                f"⏱️  Timing: First token {first_token_time:.2f}s, Total {request_time:.2f}s"
            )
            
            # Log to MySQL
            if conversation_logger and device_id:
                try:
                    await conversation_logger.log_conversation(
                        device_id=device_id,
                        device_type=device_type or "unknown",
                        user_message=user_message,
                        ai_response=full_response,
                        model=self.model,
                        provider=self.provider,
                        response_time=request_time,
                    )
                except Exception as log_error:
                    self.logger.error(f"❌ MySQL log error: {log_error}")
            
        except Exception as e:
            self.logger.error(f"❌ Chat stream error: {e}", exc_info=True)
            yield (
                "Xin lỗi, chị gặp lỗi khi xử lý.", 
                "Xin lỗi, chị gặp lỗi khi xử lý.", 
                "vi", 
                True,
                None
            )

    async def chat(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
        music_service=None
    ) -> Dict[str, Any]:
        """
        💬 CHAT WITH FUNCTION CALLING SUPPORT + SMART SPLITTING
        
        Returns dict with:
        - response: str (full text response)
        - cleaned_response: str (for TTS)
        - language: str
        - function_call: dict (if music function called)
        - music_result: dict (if music found)
        - chunks: List[str] (✅ NEW: split response for TTS)
        """
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # ═══════════════════════════════════════════════════════════
            # STEP 1: Check for music intent (DeepSeek fallback)
            # ═══════════════════════════════════════════════════════════
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
                            'music_result': first_result,
                            'chunks': [response_text]  # ✅ Single chunk for music
                        }
            
            # ═══════════════════════════════════════════════════════════
            # STEP 2: Normal chat with function calling (OpenAI/Azure)
            # ═══════════════════════════════════════════════════════════
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
            
            # ✅ DEBUG LOGGING
            self.logger.info(f"🔍 DEBUG - About to call API with:")
            self.logger.info(f"   Model: {request_params.get('model')}")
            self.logger.info(f"   Messages count: {len(request_params.get('messages', []))}")
            self.logger.info(f"   Stream: {request_params.get('stream')}")
            self.logger.info(f"   Temperature: {request_params.get('temperature')}")
            self.logger.info(f"   Max tokens: {request_params.get('max_tokens')}")
            
            self.logger.info(f"🔍 DEBUG - Client config:")
            self.logger.info(f"   Base URL: {self.client.base_url}")
            self.logger.info(f"   API Key (first 20): {self.client.api_key[:20]}...")
            
            self.logger.info(f"🔍 EXACT REQUEST:")
            self.logger.info(f"   URL: {self.client.base_url}chat/completions")
            self.logger.info(f"   Headers: Authorization: Bearer {self.client.api_key[:20]}...")
            self.logger.info(f"   Body: {json.dumps(request_params, indent=2)}")

            # Call API
            response = await self.client.chat.completions.create(**request_params)
            # DEBUG LOGGING:
            self.logger.info(f"🔍 DEBUG - API Response:")
            self.logger.info(f"   Finish reason: {response.choices[0].finish_reason}")
            self.logger.info(f"   Message content: {response.choices[0].message.content}")
            self.logger.info(f"   Tool calls: {response.choices[0].message.tool_calls}")

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            
            # ═══════════════════════════════════════════════════════════
            # STEP 3: Handle function call (3-TIER DETECTION)
            # ═══════════════════════════════════════════════════════════

            # ─────────────────────────────────────────────────────────
            # TIER 1: Standard OpenAI function calling
            # ─────────────────────────────────────────────────────────
            if finish_reason == 'tool_calls' and message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                self.logger.info(
                    f"🎯 [TIER 1] Standard function call: {function_name}"
                    f"({json.dumps(function_args, ensure_ascii=False)})"
                )
                
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
                                'arguments': function_args,
                                'method': 'standard'
                            },
                            'music_result': first_result,
                            'chunks': [response_text]
                        }

            # ─────────────────────────────────────────────────────────
            # TIER 2: Text-based function call parsing (DeepSeek)
            # ─────────────────────────────────────────────────────────
            elif finish_reason == 'stop' and message.content and music_service:
                parsed_function = self.parse_text_function_call(message.content)
                
                if parsed_function and parsed_function['name'] == 'search_and_play_music':
                    function_args = parsed_function['arguments']
                    query = function_args.get('query')
                    max_results = function_args.get('max_results', 1)
                    
                    self.logger.info(
                        f"🎯 [TIER 2] Text-based function call: {query}"
                    )
                    
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
                                'name': 'search_and_play_music',
                                'arguments': function_args,
                                'method': 'text_parsing'
                            },
                            'music_result': first_result,
                            'chunks': [response_text]
                        }

            # ─────────────────────────────────────────────────────────
            # TIER 3: Normal response (will use keyword detection in chat_stream)
            # ─────────────────────────────────────────────────────────

            
            # ═══════════════════════════════════════════════════════════
            # STEP 4: Normal text response WITH SMART SPLITTING
            # ═══════════════════════════════════════════════════════════
            response_text = message.content or "Tôi không chắc cách trả lời câu hỏi đó."
            
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            # ✅ SPLIT LONG RESPONSES INTO CHUNKS
            chunks = self.split_long_response(response_text, max_chunk_size=150)
            
            self.logger.info(f"📊 Response split into {len(chunks)} chunks")
            for i, chunk in enumerate(chunks, 1):
                self.logger.info(f"   Chunk {i}: {len(chunk)} chars - '{chunk[:40]}...'")
            
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
                'music_result': None,
                'chunks': chunks  # ✅ RETURN CHUNKS FOR TTS
            }
        
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            
            error_text = "Xin lỗi, tôi gặp lỗi khi xử lý. Vui lòng thử lại."
            
            return {
                'response': error_text,
                'cleaned_response': error_text,
                'language': 'vi',
                'function_call': None,
                'music_result': None,
                'chunks': [error_text]  # ✅ Single chunk for error
            }

    def parse_text_function_call(self, text: str) -> Optional[Dict]:
        """
        🔍 PARSE TEXT-BASED FUNCTION CALLS (DeepSeek workaround)
        
        Some models (like DeepSeek on Azure Foundry) return function calls
        as plain text instead of structured tool_calls.
        
        Example input:
            "search_and_play_music\n{\n  \"query\": \"hà nội phố\",\n  \"max_results\": 1\n}"
        
        Returns:
            {"name": "search_and_play_music", "arguments": {...}}
            or None if not a function call
        """
        if not text:
            return None
        
        # Pattern: function_name followed by JSON
        pattern = r'^(search_and_play_music)\s*\n?\s*(\{[\s\S]*\})\s*$'
        match = re.match(pattern, text.strip())
        
        if match:
            function_name = match.group(1)
            json_str = match.group(2)
            
            try:
                arguments = json.loads(json_str)
                
                self.logger.info(
                    f"🎯 Parsed text function call: {function_name}"
                    f"({json.dumps(arguments, ensure_ascii=False)})"
                )
                
                return {
                    "name": function_name,
                    "arguments": arguments
                }
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Failed to parse function JSON: {e}")
                return None
        
        return None

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
