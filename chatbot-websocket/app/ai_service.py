"""
AI Service using OpenAI-compatible API
Supports both OpenAI and DeepSeek
"""
import logging
from typing import Optional, List, Dict
from openai import AsyncOpenAI
import httpx


class AIService:
    """AI Chat Service"""
    
    def __init__(self, api_key: str, base_url: str, model: str,
             system_prompt: str, max_context: int = 10,
             temperature: float = 0.7, max_tokens: int = 500):
        self.logger = logging.getLogger('AIService')
    
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self.max_context = max_context
        self.temperature = temperature
        self.max_tokens = max_tokens
    
        # Conversation history
        self.conversations = {}
    
        # ✅ KHỞI TẠO HTTP CLIENT NGAY
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
        self.logger.info(f"🤖 Initializing AI Service...")
        self.logger.info(f"   Model: {model}")
        self.logger.info(f"   Base URL: {base_url}")
        self.logger.info(f"✅ AI client initialized successfully")

    
    async def initialize(self):
        """Initialize the AI service"""
        try:
            # Create httpx client with proper timeout
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            
            # Initialize OpenAI client
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client,
                max_retries=2
            )
            
            self.logger.info("✅ AI Service initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI: {e}")
            raise
    
    def _get_conversation(self, device_id: str) -> List[Dict]:
        """Get conversation history for device"""
        if device_id not in self.conversations:
            self.conversations[device_id] = []
        return self.conversations[device_id]
    
    def _add_message(self, device_id: str, role: str, content: str):
        """Add message to conversation"""
        conv = self._get_conversation(device_id)
        conv.append({"role": role, "content": content})
        
        # Keep only last N messages
        if len(conv) > self.max_context:
            self.conversations[device_id] = conv[-self.max_context:]
    
    async def chat(self, message: str, language: str = 'auto', device_id: str = "default") -> Optional[str]:
        """
        Chat with AI
        
        Args:
            message: User message
            language: Language code (not used, for compatibility)
            device_id: Device identifier for conversation context
        
        Returns:
            AI response or None if failed
        """
        try:
            if not self.client:
                self.logger.error("❌ AI client not initialized")
                return None
            
            self.logger.info(f"💬 User [{device_id}]: {message}")
            
            # Add user message to history
            self._add_message(device_id, "user", message)
            
            # Get conversation history
            conv = self._get_conversation(device_id)
            
            # Build messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + conv
            
            # Call API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Get response text
            reply = response.choices[0].message.content
            
            # Add to history
            self._add_message(device_id, "assistant", reply)
            
            self.logger.info(f"🤖 AI [{device_id}]: {reply}")
            return reply
            
        except Exception as e:
            self.logger.error(f"❌ AI chat error: {e}", exc_info=True)
            return None
    
    def clear_conversation(self, device_id: str):
        """Clear conversation history"""
        if device_id in self.conversations:
            del self.conversations[device_id]
            self.logger.info(f"🗑️ Cleared conversation for {device_id}")
    
    async def test(self):
        """Test AI service"""
        self.logger.info("🧪 Testing AI service...")
        response = await self.chat("Xin chào!", "vi", "test")
        if response:
            self.logger.info(f"✅ AI test OK: {response}")
        else:
            self.logger.error("❌ AI test failed")
