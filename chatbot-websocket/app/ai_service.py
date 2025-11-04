import asyncio
import logging
import os
from openai import AsyncOpenAI
from datetime import datetime

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.provider = os.getenv('AI_PROVIDER', 'openai')
        self.model = os.getenv('AI_MODEL', 'gpt-4o-mini')
        self.api_key = os.getenv('AI_API_KEY', '')
        self.custom_prompt = os.getenv('CUSTOM_PROMPT', 
            'Bạn là trợ lý thân thiện trong trường học, hỗ trợ học sinh tiểu học.')
        
        # Context management
        self.context_enabled = os.getenv('CONTEXT_ENABLED', 'true').lower() == 'true'
        self.context_messages = int(os.getenv('CONTEXT_MESSAGES', 10))
        self.conversations = {}  # device_id -> message history
        
        # API client
        base_url = None
        if self.provider == 'deepseek':
            base_url = 'https://api.deepseek.com'
        elif os.getenv('AI_BASE_URL'):
            base_url = os.getenv('AI_BASE_URL')
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url
        )
        
        logger.info(f"🤖 AI Service initialized: {self.provider}/{self.model}")
        
    async def get_response(self, device_id: str, user_message: str) -> str:
        """
        Get AI response for user message
        Args:
            device_id: Device identifier
            user_message: User's message
        Returns:
            AI response text
        """
        try:
            # Initialize conversation if needed
            if device_id not in self.conversations:
                self.conversations[device_id] = [
                    {"role": "system", "content": self.custom_prompt}
                ]
            
            # Add user message
            self.conversations[device_id].append({
                "role": "user",
                "content": user_message
            })
            
            # Trim context if needed
            if self.context_enabled:
                self._trim_context(device_id)
            
            # Get AI response
            messages = self.conversations[device_id] if self.context_enabled else [
                {"role": "system", "content": self.custom_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            ai_message = response.choices[0].message.content.strip()
            
            # Save assistant message to context
            if self.context_enabled:
                self.conversations[device_id].append({
                    "role": "assistant",
                    "content": ai_message
                })
            
            # Command detection
            await self._detect_commands(device_id, ai_message)
            
            return ai_message
            
        except Exception as e:
            logger.error(f"AI error: {e}")
            return "Xin lỗi, tôi đang gặp chút vấn đề. Bạn có thể thử lại không?"
    
    def _trim_context(self, device_id: str):
        """Trim conversation context to max messages"""
        if len(self.conversations[device_id]) > self.context_messages + 1:  # +1 for system
            # Keep system message and last N messages
            system_msg = self.conversations[device_id][0]
            recent_msgs = self.conversations[device_id][-(self.context_messages):]
            self.conversations[device_id] = [system_msg] + recent_msgs
    
    async def _detect_commands(self, device_id: str, message: str):
        """Detect commands in AI response (lights, volume, etc.)"""
        message_lower = message.lower()
        
        # Simple command detection
        commands = []
        
        if any(word in message_lower for word in ['bật đèn', 'mở đèn', 'turn on light']):
            commands.append({'action': 'toggle_light', 'state': 'on'})
            
        elif any(word in message_lower for word in ['tắt đèn', 'turn off light']):
            commands.append({'action': 'toggle_light', 'state': 'off'})
        
        # Store commands for device
        if commands:
            if not hasattr(self, 'pending_commands'):
                self.pending_commands = {}
            self.pending_commands[device_id] = commands
    
    def get_pending_commands(self, device_id: str) -> list:
        """Get and clear pending commands for device"""
        if hasattr(self, 'pending_commands') and device_id in self.pending_commands:
            commands = self.pending_commands[device_id]
            del self.pending_commands[device_id]
            return commands
        return []
    
    def clear_context(self, device_id: str):
        """Clear conversation context for device"""
        if device_id in self.conversations:
            del self.conversations[device_id]
            logger.info(f"🗑️ Context cleared for {device_id}")
