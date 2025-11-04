# School Chatbot Server for Home Assistant

WebSocket-based AI chatbot server for ESP32-S3 school devices.

## Features

✅ WebSocket duplex audio streaming (PCM 16kHz)  
✅ Whisper STT (multi-language)  
✅ Edge TTS with Vietnamese voices  
✅ OpenAI / DeepSeek integration  
✅ Context-aware conversations  
✅ Voice Activity Detection (VAD)  
✅ OTA firmware updates  
✅ Command detection (lights, volume)  

## Installation

1. Add this repository to Home Assistant:
   - Go to **Supervisor** → **Add-on Store** → **⋮** → **Repositories**
   - Add: `https://github.com/paulsteigel/ha-chatbot-server`

2. Install "School Chatbot Server (WebSocket)"

3. Configure API keys and settings

4. Start the add-on

## Configuration

```yaml
ai_provider: openai  # or deepseek
ai_model: gpt-4o-mini
ai_api_key: sk-xxx
tts_voice_vi: vi-VN-HoaiMyNeural
context_enabled: true
