#!/usr/bin/with-contenv bashio

CONFIG_PATH=/data/options.json

export AI_PROVIDER=$(bashio::config 'ai_provider')
export AI_MODEL=$(bashio::config 'ai_model')
export AI_API_KEY=$(bashio::config 'ai_api_key')
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

bashio::log.info "Starting School Chatbot WebSocket Server..."
bashio::log.info "AI Provider: ${AI_PROVIDER}"
bashio::log.info "TTS Provider: ${TTS_PROVIDER}"

cd /app
exec python3 -m app.main
