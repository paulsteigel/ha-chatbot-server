#!/usr/bin/with-contenv bashio

# Get configuration
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export MODEL=$(bashio::config 'model')
export LISTENING_PORT=$(bashio::config 'listening_port')
export LANGUAGE=$(bashio::config 'language')
export TTS_VOICE=$(bashio::config 'tts_voice')
export ENABLE_WORD_FILTER=$(bashio::config 'enable_word_filter')
export ENABLE_EDUCATIONAL_MODE=$(bashio::config 'enable_educational_mode')
export POLITENESS_LEVEL=$(bashio::config 'politeness_level')
export LOG_LEVEL=$(bashio::config 'log_level')

# Log startup
bashio::log.info "Starting Kids Chatbot Server..."
bashio::log.info "Port: ${LISTENING_PORT}"
bashio::log.info "Language: ${LANGUAGE}"
bashio::log.info "Educational Mode: ${ENABLE_EDUCATIONAL_MODE}"

# Start Flask app
cd /usr/bin
python3 app.py
