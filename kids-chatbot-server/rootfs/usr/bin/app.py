import os
import json
import logging
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ===== ĐỌC CONFIG TỪ OPTIONS =====
def load_config():
    """Load configuration from Home Assistant options"""
    config_file = '/data/options.json'
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    
    # Default config
    return {
        'bot_name': 'Bạn đồng hành - Yên Hòa',
        'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
        'openai_model': 'gpt-4o-mini',
        'openai_voice': 'nova',
        'openai_language': 'vi',
        'voice_enabled': True,
        'auto_speak': True,
        'content_filter_enabled': True,
        'blocked_keywords': ['bạo lực', 'đánh nhau', 'giết'],
        'max_message_length': 500
    }

CONFIG = load_config()

# OpenAI client
OPENAI_API_KEY = CONFIG.get('openai_api_key')
OPENAI_MODEL = CONFIG.get('openai_model', 'gpt-4o-mini')
OPENAI_VOICE = CONFIG.get('openai_voice', 'nova')
OPENAI_LANGUAGE = CONFIG.get('openai_language', 'vi')
BOT_NAME = CONFIG.get('bot_name', 'Bạn đồng hành - Yên Hòa')

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

logger.info(f"Bot Name: {BOT_NAME}")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Language: {OPENAI_LANGUAGE}")
logger.info(f"Voice: {OPENAI_VOICE}")

# ===== CONTENT FILTER =====
class ContentFilter:
    def __init__(self, config):
        self.enabled = config.get('content_filter_enabled', True)
        self.blocked_keywords = [k.lower() for k in config.get('blocked_keywords', [])]
        self.max_length = config.get('max_message_length', 500)
        
        logger.info(f"Content Filter: {'Enabled' if self.enabled else 'Disabled'}")
        logger.info(f"Blocked keywords: {len(self.blocked_keywords)}")
    
    def is_safe(self, text: str) -> tuple[bool, str]:
        """Check if content is safe"""
        if not self.enabled:
            return True, ""
        
        text_lower = text.lower()
        
        # Check length
        if len(text) > self.max_length:
            return False, f"Tin nhắn quá dài (tối đa {self.max_length} ký tự)"
        
        # Check blocked keywords
        for keyword in self.blocked_keywords:
            if keyword in text_lower:
                return False, f"Nội dung không phù hợp"
        
        return True, ""
    
    def sanitize(self, text: str) -> str:
        """Clean text"""
        import re
        text = ' '.join(text.split())
        text = re.sub(r'[^\w\s.,!?áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ-]', '', text, flags=re.IGNORECASE)
        return text.strip()

content_filter = ContentFilter(CONFIG)

# ===== SYSTEM PROMPT =====
def get_system_prompt():
    """Generate system prompt"""
    age_min = 6
    age_max = 15
    
    if OPENAI_LANGUAGE == 'vi':
        return f"""Bạn là "{BOT_NAME}" - trợ lý AI thân thiện tại Trường TH & THCS Yên Hòa, Đà Bắc, Hòa Bình.

🎯 NHIỆM VỤ:
- Giúp học sinh từ {age_min}-{age_max} tuổi học tập
- Trả lời về Toán, Tiếng Anh, Khoa học, Lịch sử, Địa lý
- Giải thích đơn giản, dễ hiểu
- Khuyến khích tinh thần học tập

🧑‍🏫 PHONG CÁCH:
- Ấm áp, kiên nhẫn như thầy/cô giáo
- Dùng ví dụ thực tế gần gũi
- Khen ngợi khi đúng, động viên khi sai
- Dùng emoji vui vẻ: 📚 ✏️ 🌟 💡 👍

📝 ĐỊNH DẠNG:
- Câu ngắn gọn, dễ hiểu
- Giải thích từng bước
- Kết thúc bằng câu hỏi hoặc khuyến khích

⚠️ NGUYÊN TẮC:
- KHÔNG đề cập bạo lực, kinh dị, người lớn
- KHÔNG nói chính trị, tôn giáo nhạy cảm
- NẾU câu hỏi không phù hợp: "Em ơi, câu hỏi này không phù hợp. Em hỏi thầy/cô giáo nhé!"

Hãy nhiệt tình và hữu ích! 🌟"""
    else:  # English
        return f"""You are "{BOT_NAME}" - a friendly AI tutor at Yen Hoa Primary & Secondary School, Da Bac, Hoa Binh.

🎯 MISSION:
- Help students aged {age_min}-{age_max} learn
- Answer Math, English, Science, History, Geography questions
- Explain simply and clearly
- Encourage learning spirit

🧑‍🏫 STYLE:
- Warm, patient like a teacher
- Use practical examples
- Praise correct answers, encourage mistakes
- Use friendly emojis: 📚 ✏️ 🌟 💡 👍

📝 FORMAT:
- Short, clear sentences
- Explain step by step
- End with question or encouragement

⚠️ RULES:
- NO violence, horror, adult content
- NO sensitive politics or religion
- IF inappropriate question: "This question isn't suitable. Please ask your teacher!"

Be enthusiastic and helpful! 🌟"""

# ===== CHAT FUNCTION =====
def chat_with_openai(message: str) -> str:
    """Chat with OpenAI"""
    if not client:
        return "Lỗi: API key chưa được cấu hình"
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI error: {str(e)}")
        return "Xin lỗi, có lỗi xảy ra. Bạn thử lại nhé! 😊"

# ===== API ENDPOINTS =====
@app.route('/')
def index():
    """Serve web interface"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'bot_name': BOT_NAME,  # ← THÊM BOT NAME
        'model': OPENAI_MODEL,
        'voice': OPENAI_VOICE,
        'language': OPENAI_LANGUAGE,
        'voice_enabled': CONFIG.get('voice_enabled', True),
        'content_filter': {
            'enabled': content_filter.enabled,
            'blocked_keywords_count': len(content_filter.blocked_keywords)
        },
        'api_key_configured': bool(OPENAI_API_KEY)
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with content filtering"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"error": "Tin nhắn không được để trống"}), 400
        
        # Sanitize input
        message = content_filter.sanitize(message)
        
        # Check safety
        is_safe, error_msg = content_filter.is_safe(message)
        if not is_safe:
            return jsonify({
                "error": error_msg,
                "response": "Xin lỗi bạn nhỏ, câu hỏi này không phù hợp. Bạn hỏi câu khác nhé! 😊"
            }), 400
        
        # Get AI response
        response = chat_with_openai(message)
        
        # Check response safety
        is_safe, error_msg = content_filter.is_safe(response)
        if not is_safe:
            logger.warning(f"Unsafe AI response filtered")
            response = "Xin lỗi, tôi không thể trả lời câu hỏi này. Bạn hỏi câu khác nhé! 😊"
        
        return jsonify({
            "response": response,
            "model": OPENAI_MODEL
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "error": str(e),
            "response": "Ối! Có lỗi xảy ra. Bạn thử lại nhé! 😊"
        }), 500

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
