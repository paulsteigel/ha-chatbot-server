#!/usr/bin/with-contenv bashio

set -e

CONFIG_PATH=/data/options.json

bashio::log.info "🚀 Starting School Chatbot WebSocket Server..."

# Activate virtual environment if exists
if [ -d "/opt/venv" ]; then
    export PATH="/opt/venv/bin:$PATH"
    bashio::log.info "✅ Virtual environment activated"
fi

# Load configuration
export AI_PROVIDER=$(bashio::config 'ai_provider')
export AI_MODEL=$(bashio::config 'ai_model')
export AI_API_KEY=$(bashio::config 'ai_api_key')
export AI_BASE_URL=$(bashio::config 'ai_base_url')
export TTS_PROVIDER=$(bashio::config 'tts_provider')
export TTS_VOICE_VI=$(bashio::config 'tts_voice_vi')
export TTS_VOICE_EN=$(bashio::config 'tts_voice_en')
export STT_MODEL=$(bashio::config 'stt_model')
export CONTEXT_ENABLED=$(bashio::config 'context_enabled')
export CONTEXT_MESSAGES=$(bashio::config 'context_messages')
export SILENCE_TIMEOUT=$(bashio::config 'silence_timeout')
export MAX_RECORDING=$(bashio::config 'max_recording_duration')
export CUSTOM_PROMPT=$(bashio::config 'custom_prompt')
export VAD_THRESHOLD=$(bashio::config 'vad_threshold')
export LOG_LEVEL=$(bashio::config 'log_level')
export PORT=5000

# Validate API key
if [ -z "$AI_API_KEY" ]; then
    bashio::log.warning "⚠️  AI API key not configured!"
fi

bashio::log.info "📋 Configuration:"
bashio::log.info "   AI Provider: ${AI_PROVIDER}"
bashio::log.info "   AI Model: ${AI_MODEL}"
bashio::log.info "   TTS Provider: ${TTS_PROVIDER}"
bashio::log.info "   STT Model: ${STT_MODEL}"

# Create data directories
mkdir -p /data/firmware
mkdir -p /data/logs

# Start application
cd /app
bashio::log.info "🎯 Starting server on port ${PORT}..."
exec python3 -m app.main 2>&1 | tee /data/logs/chatbot.log
