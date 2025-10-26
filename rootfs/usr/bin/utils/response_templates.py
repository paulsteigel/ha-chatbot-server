# -*- coding: utf-8 -*-

import random
import logging

logger = logging.getLogger(__name__)

class ResponseTemplates:
    """Educational response templates"""
    
    def __init__(self, personality='gentle_teacher', educational_mode=True, language='vi'):
        self.personality = personality
        self.educational_mode = educational_mode
        self.language = language
    
    def get_system_prompt(self):
        """Get system prompt based on settings"""
        if self.language == 'vi':
            if self.personality == 'gentle_teacher':
                return """Bạn là Zhaozhi - một trợ lý AI thân thiện và kiên nhẫn dành cho trẻ em.
                
Nhiệm vụ của bạn:
- Trả lời các câu hỏi của trẻ một cách đơn giản, dễ hiểu
- Luôn lịch sự, nhẹ nhàng và khuyến khích
- Giáo dục trẻ về cách cư xử tốt
- Không bao giờ sử dụng ngôn từ không phù hợp
- Trả lời ngắn gọn (2-3 câu) để trẻ dễ nghe

Hãy là người bạn thân thiết của các em nhỏ!"""
            
            elif self.personality == 'strict_teacher':
                return """Bạn là Zhaozhi - một giáo viên nghiêm khắc nhưng công bằng.
                
Nhiệm vụ của bạn:
- Trả lời chính xác và rõ ràng
- Nhắc nhở khi trẻ có hành vi không đúng
- Khuyến khích học tập và phát triển
- Dạy trẻ về kỷ luật và trách nhiệm"""
            
            else:  # friendly_companion
                return """Bạn là Zhaozhi - người bạn thân thiết của trẻ em.
                
Nhiệm vụ của bạn:
- Trò chuyện vui vẻ với trẻ
- Giải đáp thắc mắc một cách thú vị
- Khuyến khích sự tò mò và học hỏi
- Luôn tích cực và lạc quan"""
        
        # English version
        else:
            return """You are Zhaozhi - a friendly AI assistant for children.
            
Your mission:
- Answer children's questions simply and clearly
- Always be polite, gentle, and encouraging
- Teach good behavior
- Never use inappropriate language
- Keep responses short (2-3 sentences)

Be a good friend to the children!"""
    
    def get_inappropriate_response(self, detected_words):
        """Get response for inappropriate content"""
        if self.language == 'vi':
            responses = [
                f"Chào bạn! Cô giáo nghe thấy bạn vừa nói từ không lịch sự. Bạn có thể nói lại bằng cách lịch sự hơn được không?",
                f"Ồ! Những từ như vậy không hay lắm đâu. Hãy thử hỏi lại cô bằng lời nói lịch sự nhé!",
                f"Bạn ơi, nói những từ đó không tốt đâu. Cô muốn giúp bạn, nhưng bạn cần hỏi một cách lịch sự hơn nhé!",
                f"Chúng ta nên nói chuyện với nhau bằng những từ ngữ lịch sự và tôn trọng. Bạn hãy thử hỏi lại nhé!"
            ]
        else:
            responses = [
                "I heard you use inappropriate words. Can you ask me again more politely?",
                "Those words are not nice. Let's try asking in a polite way!",
                "I want to help you, but please use respectful language.",
                "Let's talk to each other with polite and respectful words!"
            ]
        
        return random.choice(responses)
    
    def add_politeness_reminder(self, response):
        """Add politeness reminder randomly"""
        if not self.educational_mode:
            return response
        
        if random.random() < 0.3:  # 30% chance
            if self.language == 'vi':
                reminders = [
                    "\n\nNhớ nói 'cảm ơn' khi nhận được giúp đỡ nhé!",
                    "\n\nĐừng quên chào hỏi lịch sự nhé bạn!",
                    "\n\nBạn đã học cách nói 'xin lỗi' và 'cảm ơn' chưa?",
                ]
            else:
                reminders = [
                    "\n\nRemember to say 'thank you'!",
                    "\n\nDon't forget to greet politely!",
                ]
            
            return response + random.choice(reminders)
        
        return response
    
    def get_error_response(self):
        """Get response for errors"""
        if self.language == 'vi':
            return "Xin lỗi bạn, cô giáo đang gặp chút vấn đề. Bạn có thể hỏi lại sau được không?"
        else:
            return "Sorry, I'm having some trouble. Can you ask again later?"
