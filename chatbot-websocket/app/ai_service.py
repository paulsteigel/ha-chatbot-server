"""
AI Service
Handles chat interactions with OpenAI/DeepSeek APIs
"""
import logging
import os
from typing import Optional, List, Dict
from openai import AsyncOpenAI
import httpx


class AIService:
    """AI chat service using OpenAI or DeepSeek"""
    
    def __init__(self, provider: str = 'openai', model: str = None):
        """
        Initialize AI service
        
        Args:
            provider: AI provider ('openai' or 'deepseek')
            model: Model name (optional, uses default if not provided)
        """
        self.logger = logging.getLogger('AIService')
        self.provider = provider.lower()
        
        # Configuration
        self.system_prompt = os.getenv('SYSTEM_PROMPT', 
            'Bạn là Yên Hoà, một trợ lý AI thông minh và thân thiện cho học sinh.')
        
        self.max_context = int(os.getenv('MAX_CONTEXT_MESSAGES', '10'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.7'))
        self.max_tokens = int(os.getenv('MAX_TOKENS', '500'))
        
        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize based on provider
        if self.provider == 'openai':
            self.api_key = os.getenv('OPENAI_API_KEY')
            self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            self.model = model or os.getenv('AI_MODEL', 'gpt-4o-mini')
            
        elif self.provider == 'deepseek':
            self.api_key = os.getenv('DEEPSEEK_API_KEY')
            self.base_url = 'https://api.deepseek.com/v1'
            self.model = model or os.getenv('AI_MODEL', 'deepseek-chat')
            
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
        
        if not self.api_key:
            raise ValueError(f"API key not found for provider: {provider}")
        
        self.client = None
        
        self.logger.info(f"🤖 Initializing AI Service...")
        self.logger.info(f"   Provider: {self.provider}")
        self.logger.info(f"   Model: {self.model}")
        self.logger.info(f"   Base URL: {self.base_url}")
        self.logger.info(f"   Temperature: {self.temperature}")
        self.logger.info(f"   Max Tokens: {self.max_tokens}")
        self.logger.info(f"   Max Context: {self.max_context}")
    
    async def initialize(self):
        """Initialize the AI client"""
        try:
            # Create httpx client with timeouts
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            
            # Initialize OpenAI client (works for both OpenAI and DeepSeek)
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client,
                max_retries=2
            )
            
            self.logger.info("✅ AI Service initialized")
            
            # Test the connection
            await self.test()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI Service: {e}")
            raise
    
    async def chat(self, user_message: str, language: str = 'auto') -> Optional[str]:
        """
        Send a chat message and get response
        
        Args:
            user_message: User's message
            language: Language preference ('vi', 'en', or 'auto')
        
        Returns:
            AI response text or None if failed
        """
        if not self.client:
            self.logger.error("❌ AI client not initialized")
            return None
        
        try:
            self.logger.info(f"💬 User: {user_message}")
            
            # Add user message to history
            self.conversation_history.append({
                'role': 'user',
                'content': user_message
            })
            
            # Trim history if too long
            if len(self.conversation_history) > self.max_context * 2:
                # Keep system message and recent messages
                self.conversation_history = self.conversation_history[-(self.max_context * 2):]
                self.logger.debug(f"📝 Trimmed conversation history to {len(self.conversation_history)} messages")
            
            # Build messages array
            messages = [
                {'role': 'system', 'content': self.system_prompt}
            ] + self.conversation_history
            
            # Call AI API
            self.logger.debug(f"🔄 Calling {self.provider} API...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract response
            ai_message = response.choices[0].message.content.strip()
            
            # Add AI response to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': ai_message
            })
            
            self.logger.info(f"🤖 AI: {ai_message}")
            self.logger.debug(f"   Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}")
            
            return ai_message
            
        except Exception as e:
            self.logger.error(f"❌ AI Error: {e}", exc_info=True)
            return None
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.logger.info("🗑️ Conversation history cleared")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history.copy()
    
    def set_system_prompt(self, prompt: str):
        """Update system prompt"""
        self.system_prompt = prompt
        self.logger.info(f"💭 System prompt updated: {prompt[:50]}...")
    
    async def test(self):
        """Test AI service"""
        self.logger.info("🧪 Testing AI service...")
        
        test_message = "Hello, can you hear me?"
        response = await self.chat(test_message)
        
        if response:
            self.logger.info(f"✅ AI test successful")
            self.clear_history()  # Clear test history
        else:
            self.logger.warning("⚠️ AI test failed")
