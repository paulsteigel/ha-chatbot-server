#!/usr/bin/with-contenv bashio

bashio::log.info "🎵 Starting YouTube Audio Streaming Add-on..."

# ✅ AUTO-UPDATE yt-dlp if enabled (default: true)
if bashio::config.true 'auto_update_ytdlp'; then
    bashio::log.info "🔄 Checking for yt-dlp updates..."
    
    # Try to update, but don't fail if it doesn't work
    if pip3 install --upgrade --no-cache-dir yt-dlp 2>&1 | tee /tmp/ytdlp_update.log; then
        bashio::log.info "✅ yt-dlp updated successfully"
    else
        bashio::log.warning "⚠️ yt-dlp update failed, using existing version"
        bashio::log.warning "$(cat /tmp/ytdlp_update.log)"
    fi
else
    bashio::log.info "⏭️ Auto-update disabled, using existing yt-dlp"
fi

# Show current version
YTDLP_VERSION=$(yt-dlp --version 2>/dev/null || echo "unknown")
bashio::log.info "📦 Current yt-dlp version: ${YTDLP_VERSION}"

# Change to app directory
cd /app || {
    bashio::log.error "❌ Cannot change to /app directory"
    exit 1
}

# Start Flask server
bashio::log.info "🚀 Starting Flask server on port 5000..."
exec python3 server.py
