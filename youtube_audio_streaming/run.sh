#!/usr/bin/with-contenv bashio

bashio::log.info "Starting YouTube Audio Streaming..."

cd /app || exit 1

bashio::log.info "Starting Flask server on port 5000..."
exec python3 server.py
