"""
AI Service - Handles chat with AI providers (OpenAI/DeepSeek)
"""

import os
import logging
import time
from typing import List, Dict, Optional
from openai import AsyncOpenAI


class AIService:
    """AI Chat Service supporting multiple providers"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        system_prompt: str = "You are a helpful AI assistant.",
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_context: int = 10
    ):
        """
        Initialize AI Service
        
        Args:
            api_key: API key for the provider
            base_url: Base URL for API (OpenAI or DeepSeek)
            model: Model name
            system_prompt: System prompt for the AI
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            max_context: Maximum conversation history to keep
        """
        self.logger = logging.getLogger('AIService')
        
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_context = max_context
        
        # Detect provider
        self.provider = 'deepseek' if 'deepseek' in base_url.lower() else 'openai'
        
        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
        self.logger.info("🤖 Initializing AI Service...")
        self.logger.info(f"   Provider: {self.provider}")
        self.logger.info(f"   Model: {model}")
        self.logger.info(f"   Base URL: {base_url}")
        self.logger.info(f"   Temperature: {temperature}")
        self.logger.info(f"   Max Tokens: {max_tokens}")
        self.logger.info(f"   Max Context: {max_context}")
        
        # Initialize OpenAI client
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            self.logger.info("✅ AI Service initialized")
            
            # Test the service
            self._test_service()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AI client: {e}")
            raise
    
    def _test_service(self):
        """Test AI service with a simple query"""
        import asyncio
        
        self.logger.info("🧪 Testing AI service...")
        
        async def test():
            response = await self.chat("Hello, can you hear me?")
            self.logger.info(f"🤖 AI: {response}")
            self.clear_history()
            return response
        
        try:
            # Run test in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                asyncio.create_task(test())
            else:
                # If no loop is running, run it
                asyncio.run(test())
            
            self.logger.info("✅ AI test successful")
        except Exception as e:
            self.logger.warning(f"⚠️ AI test skipped: {e}")
    
    
    async def chat(
    self, 
    user_message: str,
    conversation_logger=None,
    device_id: str = None,
    device_type: str = None
) -> str:
    """
    Send a chat message and get AI response
    
    Args:
        user_message: User's message
        conversation_logger: Optional MySQL logger instance
        device_id: Optional device ID for logging
        device_type: Optional device type for logging
    
    Returns:
        AI's response text
    """
    # Start total timer
    start_time = time.time()
    
    try:
        # Log user message
        self.logger.info(f"💬 User: {user_message}")
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Limit conversation history
        if len(self.conversation_history) > self.max_context * 2:
            self.conversation_history = self.conversation_history[-(self.max_context * 2):]
        
        # Prepare messages
        messages = [
            {"role": "system", "content": self.system_prompt}
        ] + self.conversation_history
        
        # Start API request timer
        request_start = time.time()
        self.logger.info(f"⏱️  Sending request to {self.provider.upper()}...")
        
        # ✅ USE STREAMING FOR FASTER FIRST TOKEN
        if self.provider == 'deepseek':
            # Streaming response (faster perceived speed)
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True  # ← Enable streaming
            )
            
            ai_response = ""
            first_token_time = None
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    ai_response += content
                    
                    # Log first token time
                    if first_token_time is None:
                        first_token_time = time.time() - request_start
                        self.logger.info(f"⚡ First token: {first_token_time:.2f}s")
            
        else:
            # Non-streaming (OpenAI/Groq)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            ai_response = response.choices[0].message.content
        
        # Calculate request time
        request_time = time.time() - request_start
        
        # Add AI response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": ai_response
        })
        
        # Calculate total time
        total_time = time.time() - start_time
        
        # Enhanced logging with timing
        self.logger.info(f"🤖 AI: {ai_response}")
        self.logger.info(f"⏱️  AI Response Time: {request_time:.2f}s (Total: {total_time:.2f}s)")
        
        # Warning if slow
        if request_time > 5.0:
            self.logger.warning(f"⚠️  Slow AI response detected! ({request_time:.2f}s)")
        
        # Save to MySQL if logger provided
        if conversation_logger and device_id:
            try:
                await conversation_logger.log_conversation(
                    device_id=device_id,
                    device_type=device_type or "unknown",
                    user_message=user_message,
                    ai_response=ai_response,
                    model=self.model,
                    provider=self.provider,
                    response_time=request_time
                )
            except Exception as log_error:
                self.logger.error(f"❌ MySQL log error: {log_error}")
        
        return ai_response
        
    except Exception as e:
        self.logger.error(f"❌ Chat error: {e}", exc_info=True)
        error_time = time.time() - start_time
        self.logger.error(f"⏱️  Failed after {error_time:.2f}s")
        return "Xin lỗi, chị gặp lỗi khi xử lý câu hỏi của em."

    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.logger.info("🗑️ Conversation history cleared")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history.copy()
    
    def get_context_size(self) -> int:
        """Get current context size"""
        return len(self.conversation_history)
