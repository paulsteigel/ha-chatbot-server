#!/usr/bin/with-contenv bashio

# Get config values
LOG_LEVEL=$(bashio::config 'log_level')
CACHE_DURATION=$(bashio::config 'cache_duration')

bashio::log.info "Starting HA Entity Resolver..."
bashio::log.info "Log level: ${LOG_LEVEL}"
bashio::log.info "Cache duration: ${CACHE_DURATION}s"

# Export config as environment variables
export LOG_LEVEL
export CACHE_DURATION

# Start Python application
cd /usr/bin
exec python3 -u app.py
