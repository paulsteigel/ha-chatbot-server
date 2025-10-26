#!/usr/bin/with-contenv bashio
bashio::log.info "Starting Kids ChatBot Server..."

# Get configuration
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export PORT=$(bashio::config 'port')
export LANGUAGE=$(bashio::config 'language')
export MODEL=$(bashio::config 'model')
export MAX_TOKENS=$(bashio::config 'max_tokens')
export TEMPERATURE=$(bashio::config 'temperature')
export VOICE=$(bashio::config 'voice')
export CONTENT_FILTER_ENABLED=$(bashio::config 'content_filter_enabled')
export LOG_LEVEL=$(bashio::config 'log_level')

# Validate API key
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.fatal "OpenAI API key is not configured!"
    exit 1
fi

bashio::log.info "Configuration loaded successfully"
bashio::log.info "Model: $MODEL | Language: $LANGUAGE | Voice: $VOICE"

# Start the application
cd /usr/bin
exec python3 app.py
