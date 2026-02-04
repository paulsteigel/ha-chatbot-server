# app/tools/__init__.py
"""
Đăng ký tất cả tools cho chatbot
"""

from app.tool_registry import tool_registry, ToolType

# ═══════════════════════════════════════════════════════════
# 🎵 MUSIC TOOLS
# ═══════════════════════════════════════════════════════════

def register_music_tools(music_service):
    """Đăng ký music tools"""
    
    tool_registry.register(
        name="play_music",
        description="Phát nhạc từ YouTube. Dùng khi user muốn nghe nhạc.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Tên bài hát hoặc nghệ sĩ. Nếu user không chỉ định thì dùng 'random'"
                }
            },
            "required": ["query"]
        },
        handler=lambda params: handle_play_music(music_service, params),
        tool_type=ToolType.MUSIC,
        keywords=[
            "phát nhạc", "play music", "mở nhạc", "bật nhạc",
            "nghe nhạc", "tìm bài hát", "search song"
        ],
        examples=[
            "User: 'Phát nhạc hà nội phố' → query='hà nội phố'",
            "User: 'Play the tempest piano' → query='the tempest piano'",
            "User: 'Mở nhạc' → query='random'"
        ]
    )
    
    tool_registry.register(
        name="control_music",
        description="Điều khiển nhạc đang phát (dừng, tạm dừng, tiếp tục)",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["stop", "pause", "resume", "next", "previous"],
                    "description": "Hành động cần thực hiện"
                }
            },
            "required": ["action"]
        },
        handler=lambda params: handle_control_music(params),
        tool_type=ToolType.MUSIC,
        keywords=[
            "dừng nhạc", "stop music", "tắt nhạc",
            "tạm dừng", "pause", "tiếp tục", "resume"
        ],
        examples=[
            "User: 'Dừng nhạc' → action='stop'",
            "User: 'Tạm dừng' → action='pause'"
        ]
    )

# ═══════════════════════════════════════════════════════════
# 🔊 DEVICE CONTROL TOOLS
# ═══════════════════════════════════════════════════════════

def register_device_tools(device_manager):
    """Đăng ký device control tools"""
    
    tool_registry.register(
        name="set_volume",
        description="Điều chỉnh âm lượng loa. Có thể set giá trị cụ thể hoặc tăng/giảm.",
        parameters={
            "type": "object",
            "properties": {
                "volume": {
                    "type": "string",
                    "description": "Giá trị âm lượng (0-100) hoặc '+10'/'-10' để tăng/giảm"
                }
            },
            "required": ["volume"]
        },
        handler=lambda params: handle_set_volume(device_manager, params),
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=[
            "âm lượng", "volume", "to hơn", "nhỏ hơn",
            "tăng âm lượng", "giảm âm lượng"
        ],
        examples=[
            "User: 'Tăng âm lượng' → volume='+10'",
            "User: 'Set volume 50' → volume='50'",
            "User: 'Giảm âm lượng xuống' → volume='-10'"
        ]
    )
    
    tool_registry.register(
        name="control_light",
        description="Bật/tắt đèn",
        parameters={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Trạng thái đèn"
                }
            },
            "required": ["state"]
        },
        handler=lambda params: handle_control_light(device_manager, params),
        tool_type=ToolType.DEVICE_CONTROL,
        keywords=[
            "bật đèn", "tắt đèn", "mở đèn", "turn on light", "turn off light"
        ],
        examples=[
            "User: 'Bật đèn' → state='on'",
            "User: 'Tắt đèn đi' → state='off'"
        ]
    )

# ═══════════════════════════════════════════════════════════
# 🎵 HANDLERS (Fuzzy matching như xiaozhi)
# ═══════════════════════════════════════════════════════════

async def handle_play_music(music_service, params):
    """Handler cho play_music với fuzzy matching"""
    query = params.get('query', 'random')
    
    if query == 'random':
        # Random song
        results = await music_service.search_music("piano music", 10)
        if results:
            import random
            song = random.choice(results)
            return {
                'success': True,
                'message': f"🎵 Đang phát: {song['title']}",
                'music_result': song
            }
    else:
        # Search with fuzzy matching
        results = await music_service.search_music(query, 5)
        
        if results:
            # Fuzzy match với query
            best_match = _find_best_music_match(query, results)
            
            return {
                'success': True,
                'message': f"🎵 Đang phát: {best_match['title']}",
                'music_result': best_match
            }
    
    return {
        'success': False,
        'message': f"❌ Không tìm thấy bài hát '{query}'"
    }

def _find_best_music_match(query: str, results: List[Dict]) -> Dict:
    """Fuzzy matching như xiaozhi (dùng difflib)"""
    best_match = results[0]
    highest_ratio = 0
    
    query_lower = query.lower()
    
    for result in results:
        title_lower = result['title'].lower()
        
        # Calculate similarity
        ratio = difflib.SequenceMatcher(None, query_lower, title_lower).ratio()
        
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = result
    
    return best_match

async def handle_control_music(params):
    """Handler cho control_music"""
    action = params.get('action')
    
    messages = {
        'stop': "🛑 Đã dừng phát nhạc",
        'pause': "⏸️ Đã tạm dừng",
        'resume': "▶️ Tiếp tục phát nhạc"
    }
    
    return {
        'success': True,
        'message': messages.get(action, "✅ Đã thực hiện"),
        'action': action
    }

async def handle_set_volume(device_manager, params):
    """Handler cho set_volume"""
    volume_str = params.get('volume')
    
    # Get current volume
    current_volume = device_manager.get_volume()
    
    # Parse volume
    if volume_str.startswith('+'):
        new_volume = min(100, current_volume + int(volume_str[1:]))
    elif volume_str.startswith('-'):
        new_volume = max(0, current_volume - int(volume_str[1:]))
    else:
        new_volume = int(volume_str)
    
    device_manager.set_volume(new_volume)
    
    return {
        'success': True,
        'message': f"🔊 Đã điều chỉnh âm lượng: {current_volume} → {new_volume}"
    }

async def handle_control_light(device_manager, params):
    """Handler cho control_light"""
    state = params.get('state')
    
    if state == 'on':
        device_manager.turn_on_light()
        return {
            'success': True,
            'message': "💡 Đã bật đèn"
        }
    else:
        device_manager.turn_off_light()
        return {
            'success': True,
            'message': "🌙 Đã tắt đèn"
        }