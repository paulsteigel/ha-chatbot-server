"""Content safety filter for kids"""
import logging

logger = logging.getLogger(__name__)

class ContentFilter:
    """Filter inappropriate content for children"""
    
    BLOCKED_KEYWORDS = [
        # Vietnamese
        'bạo lực', 'máu', 'chết', 'giết',
        # English
        'violence', 'kill', 'death', 'blood',
        # Add more as needed
    ]
    
    @staticmethod
    def is_safe(text: str) -> bool:
        """Check if text is safe for kids"""
        text_lower = text.lower()
        
        for keyword in ContentFilter.BLOCKED_KEYWORDS:
            if keyword in text_lower:
                logger.warning(f"Blocked keyword detected: {keyword}")
                return False
        
        return True
    
    @staticmethod
    def sanitize(text: str) -> str:
        """Remove or replace unsafe content"""
        if ContentFilter.is_safe(text):
            return text
        
        return "Xin lỗi, tôi không thể trả lời câu hỏi này. Hãy hỏi điều gì khác nhé! 😊"
