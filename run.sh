#!/usr/bin/with-contenv bashio

# Get config values
OPENAI_API_KEY=$(bashio::config 'openai_api_key')
LISTENING_PORT=$(bashio::config 'listening_port')
LANGUAGE=$(bashio::config 'language')
LOG_LEVEL=$(bashio::config 'log_level')

# Validate API key
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.error "OpenAI API Key is required!"
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY="$OPENAI_API_KEY"
export LISTENING_PORT="$LISTENING_PORT"
export LANGUAGE="$LANGUAGE"
export LOG_LEVEL="$LOG_LEVEL"

# Export all config as JSON for Python to read
bashio::config > /tmp/addon_config.json

bashio::log.info "Starting Kids ChatBot Server..."
bashio::log.info "Listening on port: $LISTENING_PORT"
bashio::log.info "Language: $LANGUAGE"

# Start Flask app
cd /usr/bin
python3 app.py
