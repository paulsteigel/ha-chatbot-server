#!/bin/bash
set -e

echo "🚀 Starting School Chatbot WebSocket Server..."

# Load config from Home Assistant options
CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    export AI_PROVIDER=$(jq -r '.ai_provider // "openai"' $CONFIG_PATH)
    export AI_MODEL=$(jq -r '.ai_model // "gpt-4o-mini"' $CONFIG_PATH)
    export AI_API_KEY=$(jq -r '.ai_api_key // ""' $CONFIG_PATH)
    export AI_BASE_URL=$(jq -r '.ai_base_url // ""' $CONFIG_PATH)
    export TTS_VOICE_VI=$(jq -r '.tts_voice_vi // "vi-VN-HoaiMyNeural"' $CONFIG_PATH)
    export TTS_VOICE_EN=$(jq -r '.tts_voice_en // "en-US-AriaNeural"' $CONFIG_PATH)
    export STT_MODEL=$(jq -r '.stt_model // "base"' $CONFIG_PATH)
    export CONTEXT_ENABLED=$(jq -r '.context_enabled // true' $CONFIG_PATH)
    export CONTEXT_MESSAGES=$(jq -r '.context_messages // 10' $CONFIG_PATH)
    export SILENCE_TIMEOUT=$(jq -r '.silence_timeout // 8' $CONFIG_PATH)
    export MAX_RECORDING=$(jq -r '.max_recording_duration // 30' $CONFIG_PATH)
    export CUSTOM_PROMPT=$(jq -r '.custom_prompt // "Bạn là trợ lý thân thiện"' $CONFIG_PATH)
    export VAD_THRESHOLD=$(jq -r '.vad_threshold // 0.02' $CONFIG_PATH)
    export LOG_LEVEL=$(jq -r '.log_level // "info"' $CONFIG_PATH)
else
    echo "⚠️  Config file not found, using defaults"
fi

export PORT=5000

echo "✅ Configuration loaded:"
echo "   AI Provider: ${AI_PROVIDER}"
echo "   AI Model: ${AI_MODEL}"
echo "   TTS Voice (VI): ${TTS_VOICE_VI}"
echo "   STT Model: ${STT_MODEL}"

# Create data directories
mkdir -p /data/firmware
mkdir -p /data/logs

# Start application
cd /app
exec python3 -m app.main 2>&1 | tee /data/logs/chatbot.log
