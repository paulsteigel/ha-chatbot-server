"""Content filtering for inappropriate content"""

import re

class ContentFilter:
    def __init__(self, language='vi'):
        self.language = language
        self.inappropriate_patterns = self._load_patterns()
    
    def _load_patterns(self):
        """Load inappropriate word patterns based on language"""
        patterns = {
            'vi': [
                r'\b(đồ|thằng|con)\s+(ngu|khốn|chó|lợn|điên)\b',
                r'\b(đụ|địt|fuck|shit|damn)\b',
                r'\b(giết|chết|tự tử|自殺)\b',
            ],
            'en': [
                r'\b(fuck|shit|damn|bitch|asshole)\b',
                r'\b(kill|die|suicide)\b',
            ]
        }
        return patterns.get(self.language, patterns['en'])
    
    def filter(self, text):
        """
        Check if text contains inappropriate content
        Returns: (is_safe, filtered_text)
        """
        text_lower = text.lower()
        
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return False, text
        
        return True, text
