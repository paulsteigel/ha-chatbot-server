#!/usr/bin/with-contenv bashio

# Banner
bashio::log.info "=================================="
bashio::log.info "  Kids ChatBot Server Starting"
bashio::log.info "=================================="

# Read config with error handling
if bashio::config.exists 'openai_api_key'; then
    OPENAI_API_KEY=$(bashio::config 'openai_api_key')
else
    OPENAI_API_KEY=""
fi

# Validate API Key
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.fatal "============================================"
    bashio::log.fatal "  OpenAI API Key is REQUIRED!"
    bashio::log.fatal "============================================"
    bashio::log.fatal ""
    bashio::log.fatal "Please follow these steps:"
    bashio::log.fatal "1. Go to Add-on Configuration tab"
    bashio::log.fatal "2. Enter your OpenAI API Key"
    bashio::log.fatal "3. Save and restart the add-on"
    bashio::log.fatal ""
    bashio::log.fatal "Get API Key at: https://platform.openai.com/api-keys"
    bashio::log.fatal "============================================"
    exit 1
fi

# Read other configs with defaults
LISTENING_PORT=$(bashio::config 'listening_port')
LANGUAGE=$(bashio::config 'language')
LOG_LEVEL=$(bashio::config 'log_level')
MAX_AUDIO_SIZE=$(bashio::config 'max_audio_size_mb')
ENABLE_FILTER=$(bashio::config 'enable_content_filter')
RESPONSE_VOICE=$(bashio::config 'response_voice')
BOT_PERSONALITY=$(bashio::config 'bot_personality')
EDUCATIONAL_MODE=$(bashio::config 'educational_mode')
POLITENESS_REMINDERS=$(bashio::config 'politeness_reminders')
SAVE_CONVERSATIONS=$(bashio::config 'save_conversations')

# Export for Python
export OPENAI_API_KEY="$OPENAI_API_KEY"
export LISTENING_PORT="$LISTENING_PORT"

# Create complete config file for Python
bashio::log.info "Creating configuration file..."

cat > /tmp/addon_config.json <<EOF
{
  "openai_api_key": "$OPENAI_API_KEY",
  "listening_port": $LISTENING_PORT,
  "language": "$LANGUAGE",
  "log_level": "$LOG_LEVEL",
  "max_audio_size_mb": $MAX_AUDIO_SIZE,
  "enable_content_filter": $ENABLE_FILTER,
  "response_voice": "$RESPONSE_VOICE",
  "bot_personality": "$BOT_PERSONALITY",
  "educational_mode": $EDUCATIONAL_MODE,
  "politeness_reminders": $POLITENESS_REMINDERS,
  "save_conversations": $SAVE_CONVERSATIONS,
  "bad_words_list": []
}
EOF

# Add bad words list if exists
if bashio::config.has_value 'bad_words_list'; then
    # Get the list and update JSON
    BAD_WORDS=$(bashio::config 'bad_words_list[]' | jq -R -s -c 'split("\n") | map(select(length > 0))')
    jq --argjson words "$BAD_WORDS" '.bad_words_list = $words' /tmp/addon_config.json > /tmp/addon_config_tmp.json
    mv /tmp/addon_config_tmp.json /tmp/addon_config.json
fi

# Log configuration (mask API key)
MASKED_KEY="${OPENAI_API_KEY:0:7}...${OPENAI_API_KEY: -4}"
bashio::log.info "----------------------------------------"
bashio::log.info "Configuration loaded:"
bashio::log.info "  Port: ${LISTENING_PORT}"
bashio::log.info "  Language: ${LANGUAGE}"
bashio::log.info "  Voice: ${RESPONSE_VOICE}"
bashio::log.info "  Personality: ${BOT_PERSONALITY}"
bashio::log.info "  Content Filter: ${ENABLE_FILTER}"
bashio::log.info "  Educational Mode: ${EDUCATIONAL_MODE}"
bashio::log.info "  Log Level: ${LOG_LEVEL}"
bashio::log.info "  API Key: ${MASKED_KEY} ✓"
bashio::log.info "----------------------------------------"

# Create temp directory
mkdir -p /tmp/chatbot_audio
mkdir -p /share/chatbot_logs

# Start Flask application
bashio::log.info "Starting Flask server on port ${LISTENING_PORT}..."
cd /usr/bin

# Run Python app
exec python3 -u app.py
