from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import subprocess
import logging
import re

app = Flask(__name__, static_folder='www', static_url_path='')
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """Serve static index.html"""
    return send_from_directory('www', 'index.html')

# ==================== WEB INTERFACE ENDPOINTS ====================

@app.route('/search', methods=['GET'])
def search_youtube():
    """
    Search YouTube for web interface
    Parameters:
        - q: search query
        - max_results: number of results (default: 10)
    
    Also compatible with ESP32 format:
        - query: search query (alternative parameter name)
    """
    # Support both 'q' (web) and 'query' (ESP32) parameters
    query = request.args.get('q') or request.args.get('query', '')
    max_results = int(request.args.get('max_results', 10))
    
    if not query:
        return jsonify({'error': 'Missing search query'}), 400
    
    logger.info(f"🔍 Searching YouTube: '{query}' (max: {max_results})")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': f'ytsearch{max_results}',
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            
            if 'entries' in info and len(info['entries']) > 0:
                results = []
                for video in info['entries']:
                    if video:  # Sometimes entries can be None
                        video_data = {
                            'id': video['id'],
                            'title': video['title'],
                            'channel': video.get('uploader', video.get('channel', 'Unknown')),
                            'duration': video.get('duration', 0),
                            'thumbnail': video.get('thumbnail', f"https://i.ytimg.com/vi/{video['id']}/default.jpg"),
                            'url': f"https://www.youtube.com/watch?v={video['id']}"
                        }
                        results.append(video_data)
                
                logger.info(f"✅ Found {len(results)} results")
                
                # Return format compatible with both web and ESP32
                response = {
                    'success': True,
                    'results': results,
                    'count': len(results)
                }
                
                # If ESP32 requests single result, also include these fields
                if len(results) > 0:
                    first = results[0]
                    response['video_id'] = first['id']
                    response['title'] = first['title']
                    response['artist'] = first['channel']
                    response['audio_url'] = f"/stream?video_id={first['id']}"
                
                return jsonify(response)
            else:
                logger.warning("❌ No results found")
                return jsonify({'error': 'No results found', 'success': False}), 404
    
    except Exception as e:
        logger.error(f"❌ Search error: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/stream', methods=['GET'])
def stream_audio():
    """
    Stream MP3 audio from YouTube
    Compatible with both web player and ESP32
    
    Parameters:
        - video_id: YouTube video ID
    
    Format: MP3 @ 24kHz mono 64kbps (ESP32 Helix decoder compatible)
    """
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    # Validate video_id format
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        return jsonify({'error': 'Invalid video_id format'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"🎵 Streaming: {video_url}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
            logger.info(f"📡 Audio URL obtained: {audio_url[:100]}...")
            
            # Stream MP3 format (compatible with ESP32 Helix decoder)
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', audio_url,
                '-vn',                    # No video
                '-acodec', 'libmp3lame',  # MP3 codec
                '-ar', '24000',           # 24kHz sample rate
                '-ac', '1',               # Mono channel
                '-b:a', '64k',           # 64kbps bitrate
                '-f', 'mp3',             # MP3 format
                '-'                       # Output to stdout
            ]
            
            logger.info(f"🎬 Starting FFmpeg process")
            
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8  # 100MB buffer
            )
            
            def generate():
                chunk_count = 0
                bytes_sent = 0
                
                try:
                    while True:
                        chunk = process.stdout.read(8192)  # 8KB chunks
                        if not chunk:
                            logger.info(f"✅ Stream complete: {chunk_count} chunks, {bytes_sent} bytes")
                            break
                        
                        chunk_count += 1
                        bytes_sent += len(chunk)
                        
                        # Log first chunk
                        if chunk_count == 1:
                            logger.info(f"📤 First chunk sent: {len(chunk)} bytes")
                            # Check MP3 header
                            if len(chunk) >= 4:
                                header = ' '.join(f'{b:02X}' for b in chunk[:4])
                                logger.info(f"🔍 Header bytes: {header}")
                        
                        # Periodic logging
                        if chunk_count % 100 == 0:
                            logger.info(f"📊 Progress: {chunk_count} chunks, {bytes_sent/1024:.1f} KB")
                        
                        yield chunk
                
                except GeneratorExit:
                    logger.info(f"⚠️ Client disconnected: {chunk_count} chunks sent")
                except Exception as e:
                    logger.error(f"❌ Stream error: {e}")
                finally:
                    process.kill()
                    process.wait()
                    logger.info(f"🛑 FFmpeg process terminated")
            
            response = Response(generate(), mimetype='audio/mpeg')
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            # Add CORS headers for web player
            response.headers['Access-Control-Allow-Origin'] = '*'
            
            return response
    
    except Exception as e:
        logger.error(f"❌ Stream error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== ESP32 COMPATIBILITY ENDPOINTS ====================

@app.route('/stream_pcm', methods=['GET'])
def stream_pcm_compatible():
    """
    Compatibility endpoint for esp32_music format
    Returns metadata and audio_url for streaming
    
    Parameters:
        - song: song name
        - artist: artist name (optional)
    """
    song = request.args.get('song', '')
    artist = request.args.get('artist', '')
    
    if not song:
        return jsonify({'error': 'Missing song parameter'}), 400
    
    # Search for the song
    query = f"{song} {artist}".strip()
    logger.info(f"🎵 ESP32 /stream_pcm request: '{query}'")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                
                # Return metadata (esp32_music compatible format)
                result = {
                    'success': True,
                    'title': video['title'],
                    'artist': video.get('uploader', 'Unknown'),
                    'audio_url': f"/stream?video_id={video['id']}",
                    'duration': video.get('duration', 0),
                    'video_id': video['id']
                }
                
                logger.info(f"✅ Found: {video['title']} ({video['id']})")
                return jsonify(result)
            else:
                logger.warning("❌ No results found")
                return jsonify({'error': 'No results found'}), 404
    
    except Exception as e:
        logger.error(f"❌ Legacy stream_pcm error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/direct_url', methods=['GET'])
def get_direct_url():
    """
    Get direct audio URL (for debugging/alternative playback)
    """
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id'}), 400
    
    try:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return jsonify({
                'success': True,
                'direct_url': info['url'],
                'format': info.get('format_note', 'unknown')
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== HEALTH CHECK ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'YouTube Audio Streaming Server',
        'endpoints': {
            'web_search': '/search?q=query&max_results=10',
            'esp32_search': '/search?query=song',
            'stream': '/stream?video_id=xxx',
            'esp32_compat': '/stream_pcm?song=xxx&artist=xxx'
        }
    })

if __name__ == '__main__':
    logger.info("🚀 Starting YouTube Audio Streaming Server")
    logger.info("📡 Endpoints:")
    logger.info("   - Web interface: http://localhost:5000/")
    logger.info("   - Search: /search?q=xxx")
    logger.info("   - Stream: /stream?video_id=xxx")
    logger.info("   - ESP32 compat: /stream_pcm?song=xxx")
    
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=True, 
        threaded=True
    )
