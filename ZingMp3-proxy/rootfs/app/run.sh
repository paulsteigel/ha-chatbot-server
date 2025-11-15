#!/usr/bin/with-contenv bashio

bashio::log.info "Starting ZingMp3-proxy..."
bashio::log.info "Author: Đặng Đình Ngọc"

# Get configuration
PORT=$(bashio::config 'port')
LOG_LEVEL=$(bashio::config 'log_level')

export PORT="${PORT}"
export LOG_LEVEL="${LOG_LEVEL}"

bashio::log.info "Port: ${PORT}"
bashio::log.info "Log Level: ${LOG_LEVEL}"

# Change to app directory
cd /app

# Start the application
bashio::log.info "Starting Node.js application..."
exec npm start
