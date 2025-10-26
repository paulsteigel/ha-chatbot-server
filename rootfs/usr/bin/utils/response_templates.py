"""Response templates for different scenarios"""

class ResponseTemplates:
    def __init__(self, language='vi'):
        self.language = language
    
    def get_system_prompt(self):
        """Get system prompt based on language"""
        prompts = {
            'vi': """Bạn là trợ lý AI thân thiện và hữu ích cho trẻ em.
Hãy trả lời bằng tiếng Việt một cách đơn giản, dễ hiểu và vui vẻ.
Luôn khuyến khích sự tò mò và học hỏi.
Không bao giờ cung cấp thông tin không phù hợp với trẻ em.""",
            
            'en': """You are a friendly and helpful AI assistant for children.
Answer in English in a simple, easy-to-understand, and cheerful way.
Always encourage curiosity and learning.
Never provide inappropriate content for children."""
        }
        return prompts.get(self.language, prompts['en'])
    
    def get_inappropriate_content_response(self):
        """Get response for inappropriate content"""
        responses = {
            'vi': "Xin lỗi bạn nhỏ, câu hỏi này không phù hợp. Hãy hỏi điều gì đó vui vẻ và bổ ích hơn nhé! 😊",
            'en': "Sorry kiddo, that question isn't appropriate. Let's talk about something fun and helpful instead! 😊"
        }
        return responses.get(self.language, responses['en'])
