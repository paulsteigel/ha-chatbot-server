"""Content filtering utilities"""

def is_safe_content(text):
    """
    Basic content filter for inappropriate content
    Returns True if content is safe, False otherwise
    """
    
    # List of inappropriate keywords (expand as needed)
    inappropriate_keywords = [
        # English
        'violence', 'weapon', 'drug', 'alcohol', 'kill', 'death', 'blood',
        'sex', 'porn', 'nude', 'hate', 'racist', 'bomb', 'terrorist',
        
        # Vietnamese
        'bạo lực', 'vũ khí', 'ma túy', 'rượu', 'giết', 'chết', 'máu',
        'sex', 'khiêu dâm', 'khỏa thân', 'ghét', 'phân biệt', 'bom', 'khủng bố',
    ]
    
    text_lower = text.lower()
    
    for keyword in inappropriate_keywords:
        if keyword in text_lower:
            return False
    
    return True


def sanitize_text(text):
    """
    Sanitize text by removing potentially harmful content
    Returns cleaned text
    """
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove special characters that might be used for injection
    dangerous_chars = ['<', '>', '{', '}', '`', '$']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text.strip()
