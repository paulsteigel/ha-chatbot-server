from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import subprocess
import logging

app = Flask(__name__, static_folder='www', static_url_path='')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    return send_from_directory('www', 'index.html')

@app.route('/search', methods=['GET'])
def search_youtube():
    """
    Search YouTube and return first matching result
    Compatible with ESP32 music_controller
    """
    query = request.args.get('query', '')
    
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    logger.info(f"Searching YouTube for: {query}")
    
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
                result = {
                    'success': True,
                    'video_id': video['id'],
                    'title': video['title'],
                    'duration': video.get('duration', 0),
                    'uploader': video.get('uploader', 'Unknown'),
                    # Add audio_url for compatibility with esp32_music format
                    'audio_url': f"/stream?video_id={video['id']}"
                }
                logger.info(f"Found: {video['title']} ({video['id']})")
                return jsonify(result)
            else:
                return jsonify({'error': 'No results found'}), 404
    
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream', methods=['GET'])
def stream_audio():
    """
    Stream MP3 audio from YouTube
    Format: MP3 @ 24kHz mono (compatible with ESP32 Helix decoder)
    """
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Streaming video: {video_url}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
            # Stream MP3 format (compatible with Helix decoder)
            # Same settings as esp32_music server
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', audio_url,
                '-vn',                    # No video
                '-acodec', 'libmp3lame',  # MP3 codec (NOT Opus!)
                '-ar', '24000',           # 24kHz sample rate
                '-ac', '1',               # Mono channel
                '-b:a', '64k',           # 64kbps bitrate
                '-f', 'mp3',             # MP3 format
                '-'                       # Output to stdout
            ]
            
            logger.info(f"Starting FFmpeg process for {video_id}")
            
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            def generate():
                try:
                    chunk_count = 0
                    while True:
                        chunk = process.stdout.read(8192)
                        if not chunk:
                            logger.info(f"Stream complete for {video_id} ({chunk_count} chunks)")
                            break
                        chunk_count += 1
                        yield chunk
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                finally:
                    process.kill()
                    process.wait()
            
            response = Response(generate(), mimetype='audio/mpeg')
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            
            return response
    
    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream_pcm', methods=['GET'])
def stream_pcm_compatible():
    """
    Compatibility endpoint for esp32_music format
    Redirects to /stream endpoint
    """
    song = request.args.get('song', '')
    artist = request.args.get('artist', '')
    
    if not song:
        return jsonify({'error': 'Missing song parameter'}), 400
    
    # Search for the song
    query = f"{song} {artist}".strip()
    logger.info(f"Legacy /stream_pcm request: {query}")
    
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
                    'duration': video.get('duration', 0)
                }
                
                return jsonify(result)
            else:
                return jsonify({'error': 'No results found'}), 404
    
    except Exception as e:
        logger.error(f"Legacy stream_pcm error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
