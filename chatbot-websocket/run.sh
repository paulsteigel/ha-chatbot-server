#!/usr/bin/with-contenv bashio

# Get config from options
export AI_PROVIDER=$(bashio::config 'ai_provider')
export AI_MODEL=$(bashio::config 'ai_model')
export TTS_VOICE_VI=$(bashio::config 'tts_voice_vi')
export TTS_VOICE_EN=$(bashio::config 'tts_voice_en')
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export OPENAI_BASE_URL=$(bashio::config 'openai_base_url')

# ✅ REMOVE: LOG_LEVEL export or set valid default
# export LOG_LEVEL="NULL"  <-- DELETE THIS

# Display config
bashio::log.info "🚀 Starting School Chatbot WebSocket Server..."
bashio::log.info "📋 Configuration:"
bashio::log.info "   AI Provider: ${AI_PROVIDER}"
bashio::log.info "   AI Model: ${AI_MODEL}"
bashio::log.info "   TTS Voice (VI): ${TTS_VOICE_VI}"

bashio::log.info "🎯 Starting server on port 5000..."

# Run application
exec python3 -m app.main
