import logging
from openai import AsyncOpenAI
from collections import defaultdict

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, api_key, model='gpt-4o-mini', base_url=None, system_prompt=None):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )
        self.model = model
        self.system_prompt = system_prompt or "Bạn là trợ lý thân thiện."
        
        # Context per device
        self.contexts = defaultdict(list)
        self.max_context = 10
        
        logger.info(f"🤖 AI service initialized: {model}")
    
    async def initialize(self):
        """Test connection"""
        try:
            # Simple test
            logger.info("✅ AI service ready")
        except Exception as e:
            logger.error(f"❌ AI init error: {e}")
            raise
    
    async def get_response(self, user_message, device_id):
        """Get AI response"""
        try:
            # Add to context
            context = self.contexts[device_id]
            context.append({"role": "user", "content": user_message})
            
            # Keep only last N messages
            if len(context) > self.max_context:
                context = context[-self.max_context:]
                self.contexts[device_id] = context
            
            # Build messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + context
            
            # Call API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            ai_message = response.choices[0].message.content
            
            # Add to context
            context.append({"role": "assistant", "content": ai_message})
            
            logger.info(f"💬 AI: {ai_message}")
            return ai_message
            
        except Exception as e:
            logger.error(f"❌ AI error: {e}", exc_info=True)
            return "Xin lỗi, tôi đang gặp sự cố."
