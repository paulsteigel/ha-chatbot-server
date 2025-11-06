"""
AI Service - Handles chat with AI providers (OpenAI/DeepSeek)
Streaming support with sentence-level chunking
"""

import os
import logging
import time
import re
from typing import List, Dict, Optional, AsyncGenerator
from openai import AsyncOpenAI


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

        # Detect provider
        self.provider = "deepseek" if "deepseek" in base_url.lower() else "openai"

        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []

        self.logger.info("🤖 Initializing AI Service...")
        self.logger.info(f"   Provider: {self.provider}")
        self.logger.info(f"   Model: {model}")
        self.logger.info(f"   Streaming: Enabled")

        try:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.logger.info("✅ AI Service initialized")
            self._test_service()
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI client: {e}")
            raise

    def _test_service(self):
        """Test AI service"""
        import asyncio

        async def test():
            response, _ = await self.chat("Hello")
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

    def clean_text_for_tts(self, text: str) -> str:
        """
        Clean text for TTS:
        - Remove ALL emoji (including complex ones)
        - Remove special symbols
        - Normalize whitespace
        - Keep Vietnamese diacritics
        """
        # Comprehensive emoji removal
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+",
            flags=re.UNICODE
        )
        
        # Remove emoji
        cleaned = emoji_pattern.sub('', text)
        
        # Remove extra punctuation (keep Vietnamese)
        cleaned = re.sub(r'[^\w\s\.,!?;:\-àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]', '', cleaned)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        if text != cleaned:
            removed = text.replace(cleaned, '').strip()
            if removed:
                self.logger.debug(f"🧹 Removed: {removed[:30]}")
        
        return cleaned.strip()

    def detect_language(self, text: str) -> str:
        """
        Detect language with Vietnamese priority.
        Vietnamese voice can handle English, but not vice versa.
        """
        vietnamese_pattern = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]'
        
        # Any Vietnamese char → use Vietnamese voice
        if re.search(vietnamese_pattern, text):
            return "vi"
        
        # Pure English check
        ascii_letters = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.sub(r'[\s\d\W]', '', text))
        
        if total_chars > 0 and ascii_letters / total_chars > 0.7:
            return "en"
        
        # Default to Vietnamese (safe)
        return "vi"

    async def chat_stream(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
    ) -> AsyncGenerator[tuple[str, str, str, bool], None]:
        """
        Stream chat response sentence by sentence for progressive TTS.
        
        Yields:
            tuple[
                original_text: str,    # For display (with emoji)
                cleaned_text: str,     # For TTS (no emoji)
                language: str,         # "vi" or "en"
                is_last: bool          # Final chunk marker
            ]
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Limit history
            if len(self.conversation_history) > self.max_context * 2:
                self.conversation_history = self.conversation_history[-(self.max_context * 2):]
            
            # Prepare messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history
            
            request_start = time.time()
            self.logger.info(f"⏱️  Streaming from {self.provider.upper()}...")
            
            # ✅ CREATE STREAMING REQUEST
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
            
            # ✅ PROCESS STREAM TOKEN BY TOKEN
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    current_sentence += token
                    
                    # Log first token latency
                    if first_token_time is None:
                        first_token_time = time.time() - request_start
                        self.logger.info(f"⚡ First token: {first_token_time:.2f}s")
                    
                    # ✅ DETECT SENTENCE BOUNDARY
                    # Match: . ! ? and variants with optional space/newline
                    if re.search(r'[.!?。！？]\s*$', current_sentence):
                        original = current_sentence.strip()
                        
                        if original:
                            sentence_count += 1
                            
                            # ✅ CLEAN FOR TTS
                            cleaned = self.clean_text_for_tts(original)
                            
                            # Only yield if text remains after cleaning
                            if cleaned:
                                language = self.detect_language(cleaned)
                                
                                self.logger.info(
                                    f"📤 Sentence {sentence_count} ({language}): "
                                    f"'{original[:50]}{'...' if len(original) > 50 else ''}'"
                                )
                                
                                # ✅ YIELD CHUNK
                                yield (original, cleaned, language, False)
                            
                            # Reset for next sentence
                            current_sentence = ""
            
            # ✅ HANDLE REMAINING TEXT (no ending punctuation)
            if current_sentence.strip():
                original = current_sentence.strip()
                cleaned = self.clean_text_for_tts(original)
                
                if cleaned:
                    sentence_count += 1
                    language = self.detect_language(cleaned)
                    
                    self.logger.info(
                        f"📤 Final sentence {sentence_count} ({language}): "
                        f"'{original[:50]}{'...' if len(original) > 50 else ''}'"
                    )
                    
                    yield (original, cleaned, language, True)
                else:
                    # Send end marker
                    yield ("", "", "", True)
            else:
                # Send end marker
                yield ("", "", "", True)
            
            # Add AI response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
            
            # Log performance
            request_time = time.time() - request_start
            total_time = time.time() - start_time
            
            self.logger.info(
                f"🤖 Complete: {len(full_response)} chars, "
                f"{sentence_count} sentences"
            )
            self.logger.info(
                f"⏱️  Timing: First token {first_token_time:.2f}s, "
                f"Total {request_time:.2f}s"
            )
            
            # Save to database
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
            # Yield error message
            yield ("Xin lỗi, chị gặp lỗi khi xử lý.", 
                   "Xin lỗi, chị gặp lỗi khi xử lý.", 
                   "vi", 
                   True)

    async def chat(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
    ) -> tuple[str, str]:
        """
        Non-streaming chat (backward compatible).
        Collects all chunks and returns complete response.
        
        Returns:
            tuple[response_text, language]
        """
        full_response = ""
        language = "vi"
        
        async for original, cleaned, lang, is_last in self.chat_stream(
            user_message, conversation_logger, device_id, device_type
        ):
            if original:
                full_response += original + " "
                language = lang
        
        return full_response.strip(), language

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.logger.info("🗑️ Conversation history cleared")

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history.copy()

    def get_context_size(self) -> int:
        """Get current context size"""
        return len(self.conversation_history)
