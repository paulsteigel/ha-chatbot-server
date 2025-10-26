"""Response templates for different scenarios"""

class ResponseTemplates:
    """Pre-defined response templates"""
    
    GREETINGS = {
        'vi': [
            "Xin chào! Mình là trợ lý AI của bạn. Bạn cần giúp gì nào? 😊",
            "Chào bạn! Hôm nay bạn muốn học gì? 📚",
            "Hi bạn! Mình sẵn sàng giúp bạn rồi! ✨"
        ],
        'en': [
            "Hello! I'm your AI assistant. How can I help you? 😊",
            "Hi there! What would you like to learn today? 📚"
        ]
    }
    
    ERRORS = {
        'api_error': "Xin lỗi, đã có lỗi xảy ra. Hãy thử lại sau nhé! 🙏",
        'no_api_key': "Chưa cấu hình API key. Vui lòng liên hệ quản trị viên! ⚙️",
        'empty_message': "Bạn chưa nói gì cả! Hãy nói gì đó đi! 😄"
    }
    
    EDUCATIONAL = {
        'encouragement': [
            "Bạn giỏi lắm! Cố gắng tiếp nhé! 💪",
            "Tuyệt vời! Bạn đang học rất tốt! ⭐",
            "Giỏi quá! Tiếp tục phát huy nhé! 🎉"
        ]
    }
    
    @staticmethod
    def get_greeting(language='vi'):
        """Get random greeting"""
        import random
        return random.choice(ResponseTemplates.GREETINGS.get(language, ['Hello!']))
    
    @staticmethod
    def get_error(error_type='api_error'):
        """Get error message"""
        return ResponseTemplates.ERRORS.get(error_type, "An error occurred")
    
    @staticmethod
    def get_encouragement():
        """Get random encouragement"""
        import random
        return random.choice(ResponseTemplates.EDUCATIONAL['encouragement'])
