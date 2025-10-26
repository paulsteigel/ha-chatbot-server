"""Content filtering utilities for kid-safe chatbot"""
import re

# Inappropriate keywords (Vietnamese and English)
INAPPROPRIATE_KEYWORDS = [
    # Vietnamese
    'đồ chó', 'mẹ kiếp', 'đm', 'vãi', 'cặc', 'lồn', 'địt',
    # English
    'fuck', 'shit', 'damn', 'hell', 'ass', 'bitch',
    # Add more as needed
]

def is_safe_content(text: str) -> bool:
    """
    Check if the content is safe for kids
    
    Args:
        text: Input text to check
        
    Returns:
        bool: True if safe, False if inappropriate
    """
    if not text:
        return False
    
    # Convert to lowercase for checking
    text_lower = text.lower()
    
    # Check for inappropriate keywords
    for keyword in INAPPROPRIATE_KEYWORDS:
        if keyword.lower() in text_lower:
            return False
    
    # Check for excessive special characters (spam detection)
    special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\u0080-\uFFFF]', text)) / len(text)
    if special_char_ratio > 0.3:
        return False
    
    # Check for excessive capitalization (shouting)
    if len(text) > 10:
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
        if caps_ratio > 0.7:
            return False
    
    return True

def sanitize_text(text: str) -> str:
    """
    Sanitize text by removing potentially harmful content
    
    Args:
        text: Input text to sanitize
        
    Returns:
        str: Sanitized text
    """
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
