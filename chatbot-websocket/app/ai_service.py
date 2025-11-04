import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AIService:
    """AI service for chat completion"""
    
    def __init__(self, api_key, base_url, model, system_prompt, max_context=10, temperature=0.7, max_tokens=500):
        """Initialize AI service"""
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.system_prompt = system_prompt
        self.max_context = max_context
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.conversations = {}  # device_id -> messages
        logger.info(f"🤖 AI Service initialized with {model}")
    
    async def initialize(self):
        """Initialize service"""
        logger.info("✅ AI Service ready")
    
    async def chat(self, text, language='vi', device_id=None):
        """Process chat message"""
        try:
            # Get or create conversation
            if device_id not in self.conversations:
                self.conversations[device_id] = [
                    {"role": "system", "content": self.system_prompt}
                ]
            
            # Add user message
            self.conversations[device_id].append({
                "role": "user",
                "content": text
            })
            
            # Keep only recent messages
            if len(self.conversations[device_id]) > self.max_context * 2 + 1:
                self.conversations[device_id] = [
                    self.conversations[device_id][0]  # Keep system prompt
                ] + self.conversations[device_id][-(self.max_context * 2):]
            
            # Get AI response
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.conversations[device_id],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add assistant message to conversation
            self.conversations[device_id].append({
                "role": "assistant",
                "content": assistant_message
            })
            
            logger.info(f"💬 AI Response: {assistant_message[:50]}...")
            return assistant_message
            
        except Exception as e:
            logger.error(f"❌ AI Error: {e}")
            return "Xin lỗi, tôi gặp sự cố. Bạn có thể hỏi lại được không?"
    
    def clear_conversation(self, device_id):
        """Clear conversation history"""
        if device_id in self.conversations:
            del self.conversations[device_id]
            logger.info(f"🗑️ Cleared conversation for {device_id}")
