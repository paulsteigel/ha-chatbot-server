#!/usr/bin/with-contenv bashio

bashio::log.info "Starting YouTube Audio Streaming server..."

cd /app
exec python3 server.py
