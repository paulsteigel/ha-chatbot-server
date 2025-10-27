def is_safe_content(text):
    """
    Basic content filter for inappropriate content
    Returns True if content is safe, False otherwise
    """
    
    # List of inappropriate keywords (expand as needed)
    inappropriate_keywords = [
        'violence', 'weapon', 'drug', 'alcohol',
        'bạo lực', 'vũ khí', 'ma túy', 'rượu',
        # Add more keywords as needed
    ]
    
    text_lower = text.lower()
    
    for keyword in inappropriate_keywords:
        if keyword in text_lower:
            return False
    
    return True
