"""
Command Detector - Detect voice commands for device control
"""

import re
from typing import Optional, Dict
import logging


class CommandDetector:
    """Detect commands from user input"""
    
    # Command patterns (Vietnamese + English)
    COMMANDS = {
        # Volume control
        "volume_up": [
            r"tăng âm lượng", r"to lên", r"lớn tiếng", r"to hơn",
            r"volume up", r"louder", r"increase volume"
        ],
        "volume_down": [
            r"giảm âm lượng", r"nhỏ lại", r"nhỏ tiếng", r"nhỏ hơn",
            r"volume down", r"quieter", r"decrease volume"
        ],
        
        # Light control
        "light_on": [
            r"bật đèn", r"mở đèn", r"sáng đèn",
            r"turn on light", r"lights? on", r"switch on"
        ],
        "light_off": [
            r"tắt đèn", r"đèn tắt", r"tối đèn",
            r"turn off light", r"lights? off", r"switch off"
        ],
        
        # Stop/Pause
        "stop": [
            r"dừng lại", r"im đi", r"thôi", r"ngừng",
            r"stop", r"pause", r"be quiet", r"shut up"
        ],
        
        # Continue
        "continue": [
            r"tiếp tục", r"nói tiếp", r"kể tiếp",
            r"continue", r"go on", r"keep going"
        ],
        
        # Fan control
        "fan_on": [
            r"bật quạt", r"mở quạt",
            r"turn on fan", r"fan on"
        ],
        "fan_off": [
            r"tắt quạt", r"quạt tắt",
            r"turn off fan", r"fan off"
        ],
    }
    
    def __init__(self):
        self.logger = logging.getLogger('CommandDetector')
        self.logger.info("🎯 Command Detector initialized")
    
    def detect(self, text: str) -> Optional[Dict]:
        """
        Detect command from text
        
        Returns:
            Dict with command info or None if no command detected
            {
                "command": "volume_up",
                "action": "set_volume",
                "value": 10,
                "text": original text
            }
        """
        text_lower = text.lower().strip()
        
        for command, patterns in self.COMMANDS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    self.logger.info(f"🎯 Command detected: {command}")
                    return self._create_command(command, text)
        
        return None
    
    def _create_command(self, command: str, original_text: str) -> Dict:
        """Create command object"""
        
        # Map command to action
        command_map = {
            # Volume
            "volume_up": {"action": "set_volume", "value": 10},
            "volume_down": {"action": "set_volume", "value": -10},
            
            # Light
            "light_on": {"action": "set_light", "value": "on"},
            "light_off": {"action": "set_light", "value": "off"},
            
            # Stop/Continue
            "stop": {"action": "stop_speaking", "value": True},
            "continue": {"action": "continue_speaking", "value": True},
            
            # Fan
            "fan_on": {"action": "set_fan", "value": "on"},
            "fan_off": {"action": "set_fan", "value": "off"},
        }
        
        cmd_data = command_map.get(command, {"action": "unknown", "value": None})
        
        return {
            "command": command,
            "action": cmd_data["action"],
            "value": cmd_data["value"],
            "text": original_text
        }