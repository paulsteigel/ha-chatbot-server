"""Response templates for different scenarios and languages"""

TEMPLATES = {
    'system': {
        'vi': """Bạn là một trợ lý AI thân thiện dành cho trẻ em. 
Hãy trả lời một cách vui vẻ, lịch sự và phù hợp với lứa tuổi.
Sử dụng ngôn ngữ đơn giản, dễ hiểu.
Luôn khuyến khích sự tò mò và học hỏi.
Không bao giờ cung cấp thông tin không phù hợp với trẻ em.""",
        
        'en': """You are a friendly AI assistant for children.
Always respond in a cheerful, polite, and age-appropriate manner.
Use simple, easy-to-understand language.
Always encourage curiosity and learning.
Never provide inappropriate content for children.""",
        
        'ja': """あなたは子供向けのフレンドリーなAIアシスタントです。
常に明るく、礼儀正しく、年齢に適した方法で応答してください。
シンプルでわかりやすい言葉を使用してください。
常に好奇心と学習を奨励してください。
子供に不適切なコンテンツを提供しないでください。""",
        
        'ko': """당신은 어린이를 위한 친근한 AI 어시스턴트입니다.
항상 밝고 예의 바르며 연령에 적합한 방식으로 응답하세요.
간단하고 이해하기 쉬운 언어를 사용하세요.
항상 호기심과 학습을 장려하세요.
어린이에게 부적절한 콘텐츠를 제공하지 마세요.""",
        
        'zh': """你是一个为儿童设计的友好AI助手。
始终以愉快、礼貌和适合年龄的方式回应。
使用简单易懂的语言。
始终鼓励好奇心和学习。
永远不要提供不适合儿童的内容。"""
    },
    
    'inappropriate': {
        'vi': "Xin lỗi, tôi không thể trả lời câu hỏi này. Hãy thử hỏi điều gì đó khác nhé! 😊",
        'en': "Sorry, I can't answer that question. Let's try something else! 😊",
        'ja': "申し訳ありませんが、その質問には答えられません。他のことを試してみましょう！😊",
        'ko': "죄송합니다. 그 질문에는 답할 수 없습니다. 다른 것을 시도해 봅시다! 😊",
        'zh': "抱歉，我无法回答这个问题。让我们尝试其他的吧！😊"
    },
    
    'error': {
        'vi': "Ối! Có lỗi xảy ra. Hãy thử lại nhé! 😅",
        'en': "Oops! Something went wrong. Please try again! 😅",
        'ja': "おっと！何か問題が発生しました。もう一度試してください！😅",
        'ko': "앗! 문제가 발생했습니다. 다시 시도해 주세요! 😅",
        'zh': "哎呀！出了点问题。请再试一次！😅"
    },
    
    'greeting': {
        'vi': "Xin chào! Tôi là trợ lý AI của bạn. Tôi có thể giúp gì cho bạn hôm nay? 🌟",
        'en': "Hello! I'm your AI assistant. How can I help you today? 🌟",
        'ja': "こんにちは！私はあなたのAIアシスタントです。今日はどのようにお手伝いできますか？🌟",
        'ko': "안녕하세요! 저는 당신의 AI 어시스턴트입니다. 오늘 무엇을 도와드릴까요? 🌟",
        'zh': "你好！我是你的AI助手。今天我能帮你什么？🌟"
    }
}

def get_response_template(template_type: str, language: str = 'vi') -> str:
    """
    Get response template for given type and language
    
    Args:
        template_type: Type of template (system, inappropriate, error, greeting)
        language: Language code (vi, en, ja, ko, zh)
        
    Returns:
        str: Template text
    """
    if template_type not in TEMPLATES:
        template_type = 'error'
    
    if language not in TEMPLATES[template_type]:
        language = 'vi'
    
    return TEMPLATES[template_type][language]
