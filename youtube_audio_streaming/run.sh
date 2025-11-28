#!/usr/bin/with-contenv bashio
# ==============================================================================
# Start YouTube Audio Streaming service
# ==============================================================================

bashio::log.info "Starting YouTube Audio Streaming..."

cd /app || exit 1

exec python3 server.py
