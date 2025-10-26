#!/usr/bin/with-contenv bashio

set -e

# Banner
bashio::log.info "=================================="
bashio::log.info "  Kids ChatBot Server Starting"
bashio::log.info "=================================="

# Get configuration with default values
OPENAI_API_KEY=$(bashio::config 'openai_api_key' '')
LISTENING_PORT=$(bashio::config 'listening_port' '5000')
LANGUAGE=$(bashio::config 'language' 'vi')
LOG_LEVEL=$(bashio::config 'log_level' 'info')
MAX_AUDIO_SIZE=$(bashio::config 'max_audio_size_mb' '25')
ENABLE_FILTER=$(bashio::config 'enable_content_filter' 'true')
RESPONSE_VOICE=$(bashio::config 'response_voice' 'nova')
BOT_PERSONALITY=$(bashio::config 'bot_personality' 'gentle_teacher')
EDUCATIONAL_MODE=$(bashio::config 'educational_mode' 'true')
POLITENESS_REMINDERS=$(bashio::config 'politeness_reminders' 'true')
SAVE_CONVERSATIONS=$(bashio::config 'save_conversations' 'false')

# Validate required config
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "null" ]; then
    bashio::log.fatal "OpenAI API Key is required!"
    bashio::log.fatal "Please configure it in the add-on configuration tab"
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY="$OPENAI_API_KEY"
export LISTENING_PORT="$LISTENING_PORT"
export LANGUAGE="$LANGUAGE"
export LOG_LEVEL="$LOG_LEVEL"

# Create config JSON for Python
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
  "bad_words_list": $(bashio::config 'bad_words_list' | jq -c '.')
}
EOF

# Log configuration (hide API key)
bashio::log.info "Port: ${LISTENING_PORT}"
bashio::log.info "Language: ${LANGUAGE}"
bashio::log.info "Log Level: ${LOG_LEVEL}"
bashio::log.info "Voice: ${RESPONSE_VOICE}"
bashio::log.info "Personality: ${BOT_PERSONALITY}"
bashio::log.info "Content Filter: ${ENABLE_FILTER}"
bashio::log.info "Educational Mode: ${EDUCATIONAL_MODE}"
bashio::log.info "API Key: Configured ✓"

# Start Flask application
bashio::log.info "Starting Flask server..."
cd /usr/bin
exec python3 app.py
