# app/tool_registry.py
"""
Tool Registry - Unified tool management for chatbot
Supports BOTH function calling (GPT-4) AND keyword detection (DeepSeek)
"""

import re
import logging
from typing import Dict, List, Callable, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('ToolRegistry')

# ═══════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

class ToolType(Enum):
    MUSIC = "music"
    DEVICE_CONTROL = "device_control"
    SYSTEM = "system"

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict
    handler: Callable  # async function
    tool_type: ToolType
    keywords: List[str]  # For keyword detection
    examples: List[str]  # Help AI understand

# ═══════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    Unified tool registry supporting:
    1. OpenAI function calling (GPT-4, GPT-4o)
    2. Keyword detection (DeepSeek, fallback)
    3. Parameter extraction from natural language
    """
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.keyword_map: Dict[str, str] = {}  # keyword -> tool_name
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Dict,
        handler: Callable,
        tool_type: ToolType,
        keywords: List[str],
        examples: List[str]
    ):
        """Register a new tool"""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            tool_type=tool_type,
            keywords=keywords,
            examples=examples
        )
        
        self.tools[name] = tool
        
        # Map keywords to tool
        for keyword in keywords:
            self.keyword_map[keyword.lower()] = name
        
        logger.info(f"✅ Registered tool: {name} [{tool_type.value}]")
    
    # ───────────────────────────────────────────────────────────
    # KEYWORD DETECTION (for DeepSeek)
    # ───────────────────────────────────────────────────────────
    
    def detect_tool(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Detect tool from text using keywords
        
        Returns:
            (tool_name, extracted_params) or None
        """
        text_lower = text.lower()
        
        # Find matching tool
        for keyword, tool_name in self.keyword_map.items():
            if keyword in text_lower:
                tool = self.tools[tool_name]
                
                # Extract parameters
                params = self._extract_params(text, tool)
                
                if params is not None:
                    logger.info(f"🎯 Detected tool: {tool_name} with params: {params}")
                    return (tool_name, params)
        
        return None
    
    def _extract_params(self, text: str, tool: ToolDefinition) -> Optional[Dict]:
        """Extract parameters from text based on tool definition"""
        if tool.tool_type == ToolType.MUSIC:
            return self._extract_music_params(text)
        elif tool.tool_type == ToolType.DEVICE_CONTROL:
            return self._extract_device_params(text, tool)
        return {}
    
    def _extract_music_params(self, text: str) -> Dict:
        """Extract song name from text"""
        patterns = [
            r'(?:phát|play|mở|bật)\s+(?:nhạc|bài|music|song)?\s*(.+)',
            r'(?:tìm|search)\s+(?:bài\s+)?(?:hát|nhạc)\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                query = match.group(1).strip()
                # Clean up
                query = re.sub(r'(đi|nào|nhé|đê|cho tôi|cho em)$', '', query).strip()
                
                if len(query) > 2:
                    return {'query': query}
        
        return {'query': 'random'}
    
    def _extract_device_params(self, text: str, tool: ToolDefinition) -> Dict:
        """Extract device control parameters"""
        params = {}
        
        # Volume control
        if 'volume' in tool.parameters.get('properties', {}):
            numbers = re.findall(r'\d+', text)
            if numbers:
                params['volume'] = int(numbers[0])
            else:
                # Relative adjustment
                if any(kw in text.lower() for kw in ['tăng', 'lên', 'up']):
                    params['volume'] = '+10'
                elif any(kw in text.lower() for kw in ['giảm', 'xuống', 'down']):
                    params['volume'] = '-10'
        
        # Light/Fan control
        if 'action' in tool.parameters.get('properties', {}):
            if any(kw in text.lower() for kw in ['bật', 'mở', 'on']):
                params['action'] = 'on'
            elif any(kw in text.lower() for kw in ['tắt', 'off']):
                params['action'] = 'off'
        
        # Brightness control
        if 'brightness' in tool.parameters.get('properties', {}):
            numbers = re.findall(r'\d+', text)
            if numbers:
                params['brightness'] = int(numbers[0])
            else:
                if any(kw in text.lower() for kw in ['tăng', 'sáng', 'up']):
                    params['brightness'] = '+10'
                elif any(kw in text.lower() for kw in ['giảm', 'tối', 'down']):
                    params['brightness'] = '-10'
        
        return params
    
    # ───────────────────────────────────────────────────────────
    # OPENAI FUNCTION CALLING (for GPT-4)
    # ───────────────────────────────────────────────────────────
    
    def get_openai_functions(self) -> List[Dict]:
        """Export tools as OpenAI function calling format"""
        functions = []
        
        for tool in self.tools.values():
            # Build description with examples
            desc = tool.description + "\n\n**Ví dụ:**\n"
            for example in tool.examples:
                desc += f"- {example}\n"
            
            functions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": desc,
                    "parameters": tool.parameters
                }
            })
        
        return functions
    
    # ───────────────────────────────────────────────────────────
    # TOOL EXECUTION
    # ───────────────────────────────────────────────────────────
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with arguments"""
        tool = self.tools.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        try:
            # Handle relative adjustments (e.g., volume='+10')
            processed_args = self._process_arguments(arguments, tool)
            
            result = await tool.handler(processed_args)
            logger.info(f"✅ Tool executed: {name} → {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {name} → {e}")
            raise
    
    def _process_arguments(self, args: Dict, tool: ToolDefinition) -> Dict:
        """Process arguments (handle relative values like '+10', '-10')"""
        processed = args.copy()
        
        # Handle relative volume
        if 'volume' in processed and isinstance(processed['volume'], str):
            if processed['volume'].startswith(('+', '-')):
                # Need current volume from device
                # This will be handled in the tool handler
                pass
        
        return processed
    
    # ───────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ───────────────────────────────────────────────────────────
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name"""
        return self.tools.get(name)
    
    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Get all registered tools"""
        return self.tools
    
    def get_tools_by_type(self, tool_type: ToolType) -> List[ToolDefinition]:
        """Get tools by type"""
        return [t for t in self.tools.values() if t.tool_type == tool_type]


# ═══════════════════════════════════════════════════════════════════
# GLOBAL REGISTRY INSTANCE
# ═══════════════════════════════════════════════════════════════════

tool_registry = ToolRegistry()


# ═══════════════════════════════════════════════════════════════════
# TOOL REGISTRATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def register_device_tools(device_manager):
    """Register all device control tools"""
    
    # ───────────────────────────────────────────────────────────
    # Tool 1: Get Device Status (MOST IMPORTANT!)
    # ───────────────────────────────────────────────────────────
    async def get_device_status(args: Dict) -> Dict:
        """Get current device status"""
        status = {
            "volume": getattr(device_manager, 'volume', 70),
            "brightness": getattr(device_manager, 'brightness', 80),
            "light_on": getattr(device_manager, 'light_on', False),
            "fan_on": getattr(device_manager, 'fan_on', False),
            "music_playing": getattr(device_manager, 'music_playing', False),
            "connected_devices": len(getattr(device_manager, 'devices', {}))
        }
        return status
    
    tool_registry.register(
        name="device_get_status",
        description=(
            "Lấy trạng thái hiện tại của thiết bị (âm lượng, độ sáng, đèn, quạt, nhạc).\n\n"
            "**Khi nào dùng:**\n"
            "1. Trước khi điều chỉnh bất kỳ cài đặt nào\n"
            "2. Khi user hỏi về trạng thái hiện tại\n"
            "3. Là bước đầu tiên cho mọi lệnh điều khiển"
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=get_device_status,
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=["trạng thái", "status", "hiện tại", "đang"],
        examples=[
            "Âm lượng hiện tại bao nhiêu?",
            "Đèn đang bật hay tắt?",
            "Cho tôi biết trạng thái thiết bị"
        ]
    )
    
    # ───────────────────────────────────────────────────────────
    # Tool 2: Set Volume
    # ───────────────────────────────────────────────────────────
    async def set_volume(args: Dict) -> Dict:
        """Set audio volume"""
        volume = args.get('volume')
        
        # Handle relative adjustment
        if isinstance(volume, str) and volume.startswith(('+', '-')):
            current = getattr(device_manager, 'volume', 70)
            delta = int(volume)
            volume = max(0, min(100, current + delta))
        
        # Validate
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        
        # Execute
        device_manager.volume = volume
        if hasattr(device_manager, 'set_volume'):
            device_manager.set_volume(volume)
        
        return {
            "success": True,
            "volume": volume,
            "message": f"Đã đặt âm lượng thành {volume}"
        }
    
    tool_registry.register(
        name="device_set_volume",
        description=(
            "Đặt âm lượng loa (0-100).\n\n"
            "**Quan trọng:** Luôn gọi `device.get_status` trước để biết âm lượng hiện tại!"
        ),
        parameters={
            "type": "object",
            "properties": {
                "volume": {
                    "type": "integer",
                    "description": "Mức âm lượng (0-100)",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["volume"]
        },
        handler=set_volume,
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=["âm lượng", "volume", "tiếng", "to", "nhỏ"],
        examples=[
            "Tăng âm lượng lên",
            "Giảm âm lượng xuống",
            "Đặt âm lượng 80",
            "Volume 50"
        ]
    )
    
    # ───────────────────────────────────────────────────────────
    # Tool 3: Control Light
    # ───────────────────────────────────────────────────────────
    async def control_light(args: Dict) -> Dict:
        """Turn light on/off"""
        action = args.get('action', 'on')
        
        if action not in ['on', 'off']:
            raise ValueError("Action must be 'on' or 'off'")
        
        # Execute
        device_manager.light_on = (action == 'on')
        if hasattr(device_manager, 'set_light'):
            device_manager.set_light(action == 'on')
        
        return {
            "success": True,
            "light_on": action == 'on',
            "message": f"Đã {'bật' if action == 'on' else 'tắt'} đèn"
        }
    
    tool_registry.register(
        name="device_control_light",
        description="Bật/tắt đèn",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Bật hoặc tắt đèn"
                }
            },
            "required": ["action"]
        },
        handler=control_light,
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=["đèn", "light", "sáng"],
        examples=[
            "Bật đèn",
            "Tắt đèn",
            "Turn on the light"
        ]
    )
    
    # ───────────────────────────────────────────────────────────
    # Tool 4: Control Fan
    # ───────────────────────────────────────────────────────────
    async def control_fan(args: Dict) -> Dict:
        """Turn fan on/off"""
        action = args.get('action', 'on')
        
        if action not in ['on', 'off']:
            raise ValueError("Action must be 'on' or 'off'")
        
        # Execute
        device_manager.fan_on = (action == 'on')
        if hasattr(device_manager, 'set_fan'):
            device_manager.set_fan(action == 'on')
        
        return {
            "success": True,
            "fan_on": action == 'on',
            "message": f"Đã {'bật' if action == 'on' else 'tắt'} quạt"
        }
    
    tool_registry.register(
        name="device_control_fan",
        description="Bật/tắt quạt",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Bật hoặc tắt quạt"
                }
            },
            "required": ["action"]
        },
        handler=control_fan,
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=["quạt", "fan", "mát"],
        examples=[
            "Bật quạt",
            "Tắt quạt",
            "Turn on the fan"
        ]
    )
    
    # ───────────────────────────────────────────────────────────
    # Tool 5: Set Brightness
    # ───────────────────────────────────────────────────────────
    async def set_brightness(args: Dict) -> Dict:
        """Set screen brightness"""
        brightness = args.get('brightness')
        
        # Handle relative adjustment
        if isinstance(brightness, str) and brightness.startswith(('+', '-')):
            current = getattr(device_manager, 'brightness', 80)
            delta = int(brightness)
            brightness = max(0, min(100, current + delta))
        
        # Validate
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        
        # Execute
        device_manager.brightness = brightness
        if hasattr(device_manager, 'set_brightness'):
            device_manager.set_brightness(brightness)
        
        return {
            "success": True,
            "brightness": brightness,
            "message": f"Đã đặt độ sáng thành {brightness}"
        }
    
    tool_registry.register(
        name="device_set_brightness",
        description=(
            "Đặt độ sáng màn hình (0-100).\n\n"
            "**Quan trọng:** Gọi `device.get_status` trước để biết độ sáng hiện tại!"
        ),
        parameters={
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "integer",
                    "description": "Mức độ sáng (0-100)",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["brightness"]
        },
        handler=set_brightness,
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=["độ sáng", "brightness", "sáng", "tối"],
        examples=[
            "Tăng độ sáng",
            "Giảm độ sáng",
            "Đặt độ sáng 90"
        ]
    )


def register_music_tools(music_service):
    """Register all music control tools"""
    
    # ───────────────────────────────────────────────────────────
    # Tool 1: Search and Play Music
    # ───────────────────────────────────────────────────────────
    async def search_and_play_music(args: Dict) -> Dict:
        """Search and play music from YouTube"""
        query = args.get('query', '')
        max_results = args.get('max_results', 1)
        
        if not query or query == 'random':
            query = 'lofi music'
        
        # Search
        results = await music_service.search_music(query, max_results)
        
        if not results:
            return {
                "success": False,
                "message": f"Không tìm thấy bài hát: {query}"
            }
        
        first_result = results[0]
        
        return {
            "success": True,
            "music_result": first_result,
            "message": f"🎵 Đang phát: {first_result['title']} của {first_result['channel']}"
        }
    
    tool_registry.register(
        name="music_search_and_play",
        description=(
            "Tìm và phát nhạc từ YouTube.\n\n"
            "**Khi nào dùng:**\n"
            "- User nói: 'phát nhạc [tên bài]', 'play [song name]'\n"
            "- User hỏi: 'tìm bài hát [tên]', 'search for [song]'"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Tên bài hát, ca sĩ, hoặc từ khóa tìm kiếm"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Số kết quả (mặc định: 1)",
                    "default": 1
                }
            },
            "required": ["query"]
        },
        handler=search_and_play_music,
        tool_type=ToolType.MUSIC,
        keywords=["phát nhạc", "play music", "bài hát", "song", "nhạc"],
        examples=[
            "Phát nhạc hà nội phố",
            "Play the tempest piano",
            "Tìm bài tình ca Hoàng Việt"
        ]
    )
    
    # ───────────────────────────────────────────────────────────
    # Tool 2: Control Music Playback
    # ───────────────────────────────────────────────────────────
    async def control_music(args: Dict) -> Dict:
        """Control music playback"""
        action = args.get('action', 'stop')
        
        valid_actions = ['stop', 'pause', 'resume', 'next', 'previous']
        if action not in valid_actions:
            raise ValueError(f"Action must be one of: {', '.join(valid_actions)}")
        
        messages = {
            'stop': "🛑 Đã dừng phát nhạc",
            'pause': "⏸️ Đã tạm dừng nhạc",
            'resume': "▶️ Tiếp tục phát nhạc",
            'next': "⏭️ Chuyển bài tiếp theo",
            'previous': "⏮️ Quay lại bài trước"
        }
        
        return {
            "success": True,
            "action": action,
            "message": messages[action]
        }
    
    tool_registry.register(
        name="music_control",
        description="Điều khiển phát nhạc (dừng, tạm dừng, tiếp tục, bài tiếp, bài trước)",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["stop", "pause", "resume", "next", "previous"],
                    "description": "Hành động điều khiển"
                }
            },
            "required": ["action"]
        },
        handler=control_music,
        tool_type=ToolType.MUSIC,
        keywords=["dừng nhạc", "stop music", "tạm dừng", "pause", "tiếp tục", "resume"],
        examples=[
            "Dừng nhạc",
            "Tạm dừng nhạc",
            "Tiếp tục phát nhạc",
            "Bài tiếp theo"
        ]
    )
