from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import subprocess
import shlex

app = Flask(__name__, static_folder='www', static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('www', 'index.html')

@app.route('/search', methods=['GET'])
def search_youtube():
    """Tìm kiếm video trên YouTube"""
    query = request.args.get('q', '')
    max_results = int(request.args.get('max_results', 10))
    
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            
            videos = []
            for entry in search_results.get('entries', []):
                videos.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'duration': entry.get('duration'),
                    'thumbnail': entry.get('thumbnail'),
                    'channel': entry.get('channel'),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
            
            return jsonify({'results': videos})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stream', methods=['GET'])
def stream_audio():
    """Stream audio từ YouTube với FFmpeg conversion"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
            # Sử dụng FFmpeg để convert sang MP3
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', audio_url,
                '-vn',  # Không video
                '-acodec', 'libmp3lame',  # Convert to MP3
                '-ab', '128k',  # Bitrate
                '-ar', '44100',  # Sample rate
                '-f', 'mp3',  # Format
                '-'  # Output to stdout
            ]
            
            print(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
            
            # Chạy FFmpeg và stream output
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            def generate():
                try:
                    while True:
                        chunk = process.stdout.read(8192)
                        if not chunk:
                            break
                        yield chunk
                except Exception as e:
                    print(f"Stream error: {e}")
                finally:
                    process.kill()
                    process.wait()
            
            response = Response(generate(), mimetype='audio/mpeg')
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            
            return response
    
    except Exception as e:
        print(f"Error in stream_audio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
