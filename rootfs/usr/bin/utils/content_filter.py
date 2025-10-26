# -*- coding: utf-8 -*-

import re
import logging

logger = logging.getLogger(__name__)

class ContentFilter:
    """Content filter for inappropriate language"""
    
    def __init__(self, enabled=True, bad_words=None):
        self.enabled = enabled
        self.bad_words = bad_words or []
        
        # Additional default Vietnamese bad words
        self.default_bad_words = [
            "ngu", "khùng", "đồ ngu", "chết tiệt", "đồ khốn",
            "ngu ngốc", "đần độn", "điên", "ngớ ngẩn"
        ]
        
        # Combine lists
        self.all_bad_words = list(set(self.bad_words + self.default_bad_words))
        logger.info(f"Content filter initialized with {len(self.all_bad_words)} filtered words")
    
    def check(self, text):
        """Check if text contains inappropriate content"""
        if not self.enabled:
            return {"is_inappropriate": False, "detected_words": []}
        
        text_lower = text.lower()
        detected = []
        
        for bad_word in self.all_bad_words:
            if bad_word.lower() in text_lower:
                detected.append(bad_word)
        
        return {
            "is_inappropriate": len(detected) > 0,
            "detected_words": detected
        }
