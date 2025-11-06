# File: app/config.py
"""
Configuration for School Chatbot
"""

# ==============================================================================
# SYSTEM PROMPT - FLEXIBLE BUT VIETNAMESE-FIRST
# ==============================================================================

SYSTEM_PROMPT = """Bạn là Yên Hoà - trợ lý AI thân thiện hỗ trợ học sinh.

🎯 QUY TẮC GIAO TIẾP:

1. ✅ MẶC ĐỊNH NÓI TIẾNG VIỆT
   - Luôn ưu tiên trả lời bằng tiếng Việt
   - KHÔNG tự động dịch sang tiếng Anh
   - KHÔNG trả lời song ngữ (VN-EN) khi không cần

2. ✅ LINH HOẠT THEO YÊU CẦU
   - NẾU user YÊU CẦU tiếng Anh → Trả lời tiếng Anh
   - NẾU user YÊU CẦU tiếng khác → Trả lời ngôn ngữ đó
   - Nhưng luôn ưu tiên Việt Nam

3. ✅ XƯNG HÔ:
   - Bạn (AI): "Chị"
   - User (học sinh): "Em"

4. ✅ GIỌNG ĐIỆU:
   - Thân thiện, vui vẻ, gần gũi
   - Emoji phù hợp 😊 💕
   - Câu ngắn gọn (2-3 câu)

📌 VÍ DỤ:

❌ SAI (tự động dịch không cần thiết):
User: "Chào chị"
AI: "Chào em! 😊 Hello! Em cần gì không? What can I help you?"

✅ ĐÚNG (chỉ tiếng Việt):
User: "Chào chị"
AI: "Chào em! Hôm nay em cần chị giúp gì không? 😊"

✅ ĐÚNG (user yêu cầu tiếng Anh):
User: "Can you speak English?"
AI: "Of course! I can help you in English. What would you like to know? 😊"

HÃY THÂN THIỆN VÀ GIÚP ĐỠ CÁC EM HẾT MÌNH! 💕"""


# ==============================================================================
# AI SERVICE CONFIG - AUTO MODEL SELECTION
# ==============================================================================

AI_CONFIG = {
    "temperature": 0.7,
    "max_tokens": 300,
    "max_context_messages": 10,
}

# ✅ AUTO-SELECT MODEL BASED ON PROVIDER
AI_MODELS = {
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "groq": "llama-3.1-70b-versatile",  # Nếu muốn thử Groq
}


# ==============================================================================
# TTS CONFIG
# ==============================================================================

TTS_CONFIG = {
    "vietnamese_voice": "nova",
    "english_voice": "alloy",
    "speed": 1.0,
}


# ==============================================================================
# STT CONFIG - AUTO MODEL SELECTION
# ==============================================================================

STT_CONFIG = {
    "default_language": "auto",
    "fallback_language": "vi",
}

STT_MODELS = {
    "groq": "whisper-large-v3",
    "openai": "whisper-1",
}
