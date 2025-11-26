#!/usr/bin/with-contenv bashio
# ==============================================================================
# Setup and start HA Entity Resolver
# ==============================================================================

bashio::log.info "Initializing HA Entity Resolver..."

# Get config
LOG_LEVEL=$(bashio::config 'log_level' 'info')
CACHE_DURATION=$(bashio::config 'cache_duration' '60')

# Export environment variables
export LOG_LEVEL="${LOG_LEVEL}"
export CACHE_DURATION="${CACHE_DURATION}"

bashio::log.info "Log level: ${LOG_LEVEL}"
bashio::log.info "Cache duration: ${CACHE_DURATION}s"

# Start Python app in background
cd /usr/bin
python3 -u app.py &

bashio::log.info "HA Entity Resolver started"
