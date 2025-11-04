import logging
from openai import AsyncOpenAI
from collections import defaultdict

logger = logging.getLogger(__name__)

class AIService:
    """AI service with multiple provider support"""
    
    # Provider configurations
    PROVIDERS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
        },
        "deepseek-v3": {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",  # v3 uses same endpoint
            "models": ["deepseek-chat", "deepseek-reasoner"]
        }
    }
    
    def __init__(self, config):
        """Initialize AI service with provider selection"""
        self.provider = config.get('ai_provider', 'deepseek')
        
        # Get provider config
        provider_config = self.PROVIDERS.get(self.provider)
        if not provider_config:
            raise ValueError(f"Unknown AI provider: {self.provider}")
        
        # Get API key based on provider
        if self.provider.startswith('deepseek'):
            api_key = config.get('deepseek_api_key')
            model = config.get('deepseek_model', provider_config['default_model'])
        else:  # openai
            api_key = config.get('openai_api_key')
            model = config.get('openai_model', provider_config['default_model'])
        
        if not api_key:
            raise ValueError(f"API key required for provider: {self.provider}")
        
        # Initialize client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=provider_config['base_url']
        )
        
        self.model = model
        self.system_prompt = config.get('system_prompt', 
            "Bạn là trợ lý AI thân thiện, hỗ trợ cả tiếng Việt và tiếng Anh.")
        self.max_context = config.get('max_context_messages', 10)
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 500)
        
        # Context storage per device
        self.contexts = defaultdict(list)
        
        logger.info(f"✅ AI Service initialized")
        logger.info(f"   Provider: {self.provider}")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Base URL: {provider_config['base_url']}")
        logger.info(f"   Max context: {self.max_context} messages")
        logger.info(f"   Temperature: {self.temperature}")
        logger.info(f"   Max tokens: {self.max_tokens}")
    
    async def get_response(self, user_message, device_id):
        """Get AI response with context tracking"""
        try:
            logger.info(f"🤖 AI Request - Device: {device_id}")
            logger.info(f"   Provider: {self.provider}")
            logger.info(f"   Model: {self.model}")
            logger.info(f"   Message: {user_message}")
            
            # Get or create context for device
            context = self.contexts[device_id]
            
            # Add user message to context
            context.append({"role": "user", "content": user_message})
            
            # Keep only last N messages
            if len(context) > self.max_context:
                context = context[-self.max_context:]
                self.contexts[device_id] = context
            
            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + context
            
            logger.info(f"   Context length: {len(context)} messages")
            
            # Call API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            ai_message = response.choices[0].message.content
            
            # Add assistant response to context
            context.append({"role": "assistant", "content": ai_message})
            
            logger.info(f"💬 AI Response: {ai_message}")
            
            return ai_message
        
        except Exception as e:
            logger.error(f"❌ AI error: {e}", exc_info=True)
            logger.error(f"   Provider: {self.provider}")
            logger.error(f"   Model: {self.model}")
            return "Xin lỗi, tôi đang gặp sự cố. Sorry, I'm experiencing technical difficulties."
    
    def clear_context(self, device_id):
        """Clear conversation context for a device"""
        if device_id in self.contexts:
            del self.contexts[device_id]
            logger.info(f"🗑️ Cleared context for device: {device_id}")
    
    def get_context_length(self, device_id):
        """Get current context length for a device"""
        return len(self.contexts.get(device_id, []))
    
    def get_provider_info(self):
        """Get current provider information"""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.PROVIDERS[self.provider]["base_url"],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_context": self.max_context
        }
