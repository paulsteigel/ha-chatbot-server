#!/usr/bin/with-contenv bashio

# Banner
bashio::log.info "=================================="
bashio::log.info "  Kids ChatBot Server Starting"
bashio::log.info "=================================="

# Get configuration from Home Assistant
OPENAI_API_KEY=$(bashio::config 'openai_api_key')
LISTENING_PORT=$(bashio::config 'listening_port')
LANGUAGE=$(bashio::config 'language')
LOG_LEVEL=$(bashio::config 'log_level')

# Validate required config
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.fatal "OpenAI API Key is required!"
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY="$OPENAI_API_KEY"
export LISTENING_PORT="$LISTENING_PORT"
export LANGUAGE="$LANGUAGE"
export LOG_LEVEL="$LOG_LEVEL"

# Save entire config as JSON for Python to read
bashio::config > /tmp/addon_config.json

# Log configuration
bashio::log.info "Port: ${LISTENING_PORT}"
bashio::log.info "Language: ${LANGUAGE}"
bashio::log.info "Log Level: ${LOG_LEVEL}"

# Start Flask application
bashio::log.info "Starting Flask server..."
cd /usr/bin
python3 app.py
