#!/usr/bin/with-contenv bashio

# Get AI configuration
export AI_PROVIDER=$(bashio::config 'ai_provider')
export AI_MODEL=$(bashio::config 'ai_model')

# Get API keys based on provider
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export OPENAI_BASE_URL=$(bashio::config 'openai_base_url')
export DEEPSEEK_API_KEY=$(bashio::config 'deepseek_api_key')

# Get TTS settings
export TTS_VOICE_VI=$(bashio::config 'tts_voice_vi')
export TTS_VOICE_EN=$(bashio::config 'tts_voice_en')

# Get chat settings
export SYSTEM_PROMPT=$(bashio::config 'system_prompt')
export MAX_CONTEXT_MESSAGES=$(bashio::config 'max_context_messages')
export TEMPERATURE=$(bashio::config 'temperature')
export MAX_TOKENS=$(bashio::config 'max_tokens')

# Get log level (with safe default)
LOG_LEVEL_CONFIG=$(bashio::config 'log_level')
if bashio::var.has_value "${LOG_LEVEL_CONFIG}"; then
    export LOG_LEVEL="${LOG_LEVEL_CONFIG}"
else
    export LOG_LEVEL="info"
fi

# Display startup info
bashio::log.info "========================================="
bashio::log.info "🚀 ESP32 Chatbot WebSocket Server"
bashio::log.info "========================================="
bashio::log.info "📋 Configuration:"
bashio::log.info "   AI Provider: ${AI_PROVIDER}"
bashio::log.info "   AI Model: ${AI_MODEL}"
bashio::log.info "   TTS Voice (VI): ${TTS_VOICE_VI}"
bashio::log.info "   TTS Voice (EN): ${TTS_VOICE_EN}"
bashio::log.info "   Max Context: ${MAX_CONTEXT_MESSAGES}"
bashio::log.info "   Temperature: ${TEMPERATURE}"
bashio::log.info "   Max Tokens: ${MAX_TOKENS}"
bashio::log.info "   Log Level: ${LOG_LEVEL}"
bashio::log.info "========================================="

# Validate API key based on provider
if [ "${AI_PROVIDER}" = "openai" ]; then
    if ! bashio::var.has_value "${OPENAI_API_KEY}"; then
        bashio::log.fatal "❌ OpenAI API key required when using OpenAI provider!"
        exit 1
    fi
    bashio::log.info "✅ Using OpenAI with base URL: ${OPENAI_BASE_URL}"
elif [ "${AI_PROVIDER}" = "deepseek" ]; then
    if ! bashio::var.has_value "${DEEPSEEK_API_KEY}"; then
        bashio::log.fatal "❌ DeepSeek API key required when using DeepSeek provider!"
        exit 1
    fi
    bashio::log.info "✅ Using DeepSeek"
fi

bashio::log.info "🎯 Starting WebSocket server on port 5000..."

# Run application with exec (important for proper signal handling)
cd /app
exec python3 -m app.main
