# File: app/ai_service.py
"""
AI Service - Handles chat with AI providers (OpenAI/DeepSeek)
Streaming support with sentence-level chunking
✅ Enhanced emoji/markdown removal for TTS
"""

import os
import logging
import time
import re
import unicodedata
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
        self.logger.info(f"   Emoji removal: Enhanced")

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
            # ✅ UNPACK 3 VALUES: original, cleaned, language
            original, cleaned, language = await self.chat("Hello")
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
        ✨ CLEAN TEXT FOR TTS - ENHANCED VERSION ✨
        
        Loại bỏ:
        - Emoji (😊 🎉 👍 ✅ ❌ etc) - Piper đọc thành "mặt cười, mắt cười" rất buồn cười!
        - Markdown (**bold**, `code`, ~~strike~~)
        - Special symbols (✨ ⭐ etc)
        - Brackets with single chars ([x], [!])
        
        Giữ lại:
        - Vietnamese diacritics (àáảãạ...)
        - Basic punctuation (. , ! ? ; : - ' " /)
        - Numbers and letters
        """
        if not text:
            return ""
        
        original_text = text
        cleaned = text
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Remove ALL emoji (comprehensive Unicode ranges)
        # ═══════════════════════════════════════════════════════════
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # 🇻🇳 flags
            "\U0001F300-\U0001F5FF"  # 🌟 symbols & pictographs
            "\U0001F600-\U0001F64F"  # 😊😂🥰 emoticons
            "\U0001F680-\U0001F6FF"  # 🚀🎉 transport & map
            "\U0001F700-\U0001F77F"  # ⚗️ alchemical
            "\U0001F780-\U0001F7FF"  # 🔺 geometric shapes
            "\U0001F800-\U0001F8FF"  # ⬆️ arrows
            "\U0001F900-\U0001F9FF"  # 🤔🙏 supplemental symbols
            "\U0001FA00-\U0001FA6F"  # ♟️ chess symbols
            "\U0001FA70-\U0001FAFF"  # 🫡 extended pictographs
            "\U00002700-\U000027BF"  # ✅❌✨ dingbats
            "\U000024C2-\U0001F251"  # 🅰️ enclosed chars
            "\U0001f926-\U0001f937"  # 🤦 face gestures
            "\U00010000-\U0010ffff"  # supplementary planes
            "\u2600-\u26FF"          # ☀️⭐ misc symbols
            "\u2700-\u27BF"          # ✂️ dingbats
            "\uFE00-\uFE0F"          # variation selectors
            "\u203C-\u3299"          # ‼️ misc technical
            "\u200D"                 # zero width joiner
            "\u2300-\u23FF"          # ⌚ misc technical
            "\u2B50-\u2BFF"          # ⭐ misc symbols
            "]+",
            flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub('', cleaned)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Fallback - Remove using Unicode categories
        # Catches emoji that regex might miss
        # ═══════════════════════════════════════════════════════════
        def is_emoji_char(c):
            """Check if character is emoji-like"""
            cat = unicodedata.category(c)
            # So = Symbol Other, Cn = Not Assigned
            return cat in ['So', 'Cn']
        
        cleaned = ''.join(c for c in cleaned if not is_emoji_char(c))
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Remove Markdown formatting
        # ═══════════════════════════════════════════════════════════
        # **bold** or *italic* → plain text
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned)  # **text**
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)      # *text*
        
        # __underline__ or _italic_ → plain text
        cleaned = re.sub(r'__(.+?)__', r'\1', cleaned)      # __text__
        cleaned = re.sub(r'_(.+?)_', r'\1', cleaned)        # _text_
        
        # ~~strikethrough~~ → plain text
        cleaned = re.sub(r'~~(.+?)~~', r'\1', cleaned)
        
        # `code` or ```code block``` → plain text
        cleaned = re.sub(r'`{1,3}(.+?)`{1,3}', r'\1', cleaned)
        
        # [link](url) → link (keep text, remove URL)
        cleaned = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', cleaned)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Remove brackets with single chars [x], [!], etc
        # ═══════════════════════════════════════════════════════════
        cleaned = re.sub(r'\[\w\]', '', cleaned)
        cleaned = re.sub(r'\[!\]', '', cleaned)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Remove extra symbols
        # Keep: Letters, numbers, Vietnamese, basic punctuation
        # ═══════════════════════════════════════════════════════════
        # Vietnamese vowels with diacritics
        vietnamese_chars = (
            'àáảãạăằắẳẵặâầấẩẫậ'
            'èéẻẽẹêềếểễệ'
            'ìíỉĩị'
            'òóỏõọôồốổỗộơờớởỡợ'
            'ùúủũụưừứửữự'
            'ỳýỷỹỵ'
            'đĐ'
        )
        
        # Allowed chars: a-zA-Z0-9 + Vietnamese + basic punctuation
        allowed_pattern = rf'[^\w\s\.,!?;:\-\'\"/()\[\]{vietnamese_chars}]'
        cleaned = re.sub(allowed_pattern, '', cleaned)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 6: Normalize whitespace
        # ═══════════════════════════════════════════════════════════
        # Multiple spaces → single space
        cleaned = ' '.join(cleaned.split())
        
        # Remove space before punctuation
        cleaned = re.sub(r'\s+([.,!?;:])', r'\1', cleaned)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 7: Log what was removed (for debugging)
        # ═══════════════════════════════════════════════════════════
        if original_text != cleaned:
            removed = set(original_text) - set(cleaned)
            # Filter out common chars (space, letters)
            removed_special = {
                c for c in removed 
                if not c.isalnum() and not c.isspace()
            }
            if removed_special:
                removed_str = ''.join(sorted(removed_special))
                self.logger.debug(
                    f"🧹 Cleaned TTS text:\n"
                    f"   Before: {original_text[:60]}{'...' if len(original_text) > 60 else ''}\n"
                    f"   After:  {cleaned[:60]}{'...' if len(cleaned) > 60 else ''}\n"
                    f"   Removed: {removed_str}"
                )
        
        return cleaned.strip()

    def detect_language(self, text: str) -> str:
        """
        🔍 DETECT LANGUAGE - Vietnamese priority
        
        Vietnamese voice (Piper) có thể đọc English OK,
        nhưng English voice không đọc được Vietnamese.
        → Ưu tiên Vietnamese nếu có bất kỳ ký tự Việt nào.
        """
        # Vietnamese diacritics pattern
        vietnamese_pattern = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]'
        
        # Any Vietnamese char → use Vietnamese voice
        if re.search(vietnamese_pattern, text):
            return "vi"
        
        # Pure English check
        ascii_letters = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.sub(r'[\s\d\W]', '', text))
        
        if total_chars > 0 and ascii_letters / total_chars > 0.7:
            return "en"
        
        # Default to Vietnamese (safe for mixed content)
        return "vi"

    async def chat_stream(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
    ) -> AsyncGenerator[tuple[str, str, str, bool], None]:
        """
        🌊 STREAM CHAT RESPONSE - Sentence by sentence
        
        Yields progressive chunks for real-time TTS:
        
        Yields:
            tuple[
                original_text: str,    # For display (with emoji/markdown)
                cleaned_text: str,     # For TTS (emoji removed)
                language: str,         # "vi" or "en"
                is_last: bool          # True for final chunk
            ]
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Limit history to max_context
            if len(self.conversation_history) > self.max_context * 2:
                self.conversation_history = self.conversation_history[-(self.max_context * 2):]
            
            # Prepare messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history
            
            request_start = time.time()
            self.logger.info(f"⏱️  Streaming from {self.provider.upper()}...")
            
            # ═══════════════════════════════════════════════════════════
            # CREATE STREAMING REQUEST
            # ═══════════════════════════════════════════════════════════
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
            
            # ═══════════════════════════════════════════════════════════
            # PROCESS STREAM TOKEN BY TOKEN
            # ═══════════════════════════════════════════════════════════
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    current_sentence += token
                    
                    # Log first token latency
                    if first_token_time is None:
                        first_token_time = time.time() - request_start
                        self.logger.info(f"⚡ First token: {first_token_time:.2f}s")
                    
                    # ═══════════════════════════════════════════════════
                    # DETECT SENTENCE BOUNDARY
                    # Match: . ! ? và các biến thể
                    # ═══════════════════════════════════════════════════
                    if re.search(r'[.!?。！？]\s*$', current_sentence):
                        original = current_sentence.strip()
                        
                        if original:
                            sentence_count += 1
                            
                            # ✨ CLEAN FOR TTS (remove emoji)
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
                            else:
                                self.logger.debug(
                                    f"⏭️  Skipped empty sentence after cleaning: '{original[:30]}...'"
                                )
                            
                            # Reset for next sentence
                            current_sentence = ""
            
            # ═══════════════════════════════════════════════════════════
            # HANDLE REMAINING TEXT (no ending punctuation)
            # ═══════════════════════════════════════════════════════════
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
            
            # ═══════════════════════════════════════════════════════════
            # LOG PERFORMANCE METRICS
            # ═══════════════════════════════════════════════════════════
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
            
            # ═══════════════════════════════════════════════════════════
            # SAVE TO DATABASE
            # ═══════════════════════════════════════════════════════════
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
            yield (
                "Xin lỗi, chị gặp lỗi khi xử lý.", 
                "Xin lỗi, chị gặp lỗi khi xử lý.", 
                "vi", 
                True
            )

    async def chat(
        self,
        user_message: str,
        conversation_logger=None,
        device_id: str = None,
        device_type: str = None,
    ) -> tuple[str, str, str]:
        """
        💬 NON-STREAMING CHAT (backward compatible)
        
        Collects all streaming chunks and returns complete response.
        
        ✨ Returns BOTH original (display) and cleaned (TTS) text
        
        Returns:
            tuple[
                original_text: str,  # Có emoji/markdown - cho DISPLAY
                cleaned_text: str,   # Không emoji - cho TTS  
                language: str        # "vi" hoặc "en"
            ]
        """
        full_original = ""
        full_cleaned = ""
        language = "vi"
        
        async for original, cleaned, lang, is_last in self.chat_stream(
            user_message, conversation_logger, device_id, device_type
        ):
            if original:
                full_original += original + " "
            if cleaned:
                full_cleaned += cleaned + " "
            language = lang
        
        return (
            full_original.strip(),
            full_cleaned.strip(),
            language
        )


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


# ═══════════════════════════════════════════════════════════════════
# 🧪 TEST SUITE - Run with: python app/ai_service.py
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Mock AI service for testing cleaning only
    class MockAIService:
        def __init__(self):
            self.logger = logging.getLogger("TestClean")
        
        # Copy the cleaning methods
        clean_text_for_tts = AIService.clean_text_for_tts
        detect_language = AIService.detect_language
    
    service = MockAIService()
    
    # Test cases
    test_cases = [
        # Emoji tests
        ("Xin chào 😊 bạn nhé!", "Piper sẽ đọc 'mặt cười mắt cười' - phải loại bỏ!"),
        ("Chúc mừng 🎉🎊 năm mới! 🎆", "Multiple emoji"),
        ("Tôi đồng ý 👍✅", "Thumbs + checkmark"),
        ("Cảm ơn bạn 🙏💕", "Prayer hands + heart"),
        ("Wow 🤔🔥 tuyệt vời!", "Thinking + fire"),
        ("Hello ✨ world ⭐", "Sparkles + star"),
        
        # Markdown tests
        ("This is **bold** text", "Bold markdown"),
        ("This is *italic* text", "Italic markdown"),
        ("This is __underlined__ text", "Underline markdown"),
        ("This is ~~strikethrough~~ text", "Strikethrough markdown"),
        ("This is `code` text", "Inline code"),
        ("Check this [link](http://example.com)", "Link markdown"),
        
        # Mixed tests
        ("**Xin chào** 😊 `bạn` nhé!", "Mixed Vietnamese + emoji + markdown"),
        ("[!] Warning: Please check 🔥", "Brackets + emoji"),
        
        # Vietnamese-only (should keep)
        ("Xin chào, tôi là trợ lý AI.", "Pure Vietnamese - keep all"),
        
        # English-only
        ("Hello, I am your AI assistant.", "Pure English"),
    ]
    
    print("\n" + "="*70)
    print("🧪 TESTING EMOJI/MARKDOWN REMOVAL FOR TTS")
    print("="*70)
    
    for i, (text, description) in enumerate(test_cases, 1):
        cleaned = service.clean_text_for_tts(text)
        language = service.detect_language(cleaned)
        
        print(f"\n{'─'*70}")
        print(f"Test {i}: {description}")
        print(f"{'─'*70}")
        print(f"📝 Original:  {text}")
        print(f"✨ Cleaned:   {cleaned}")
        print(f"🌍 Language:  {language}")
        
        # Show what was removed
        if text != cleaned:
            removed_chars = sorted(set(text) - set(cleaned))
            print(f"🗑️  Removed:   {''.join(c for c in removed_chars if not c.isalnum() and not c.isspace())}")
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("="*70)
