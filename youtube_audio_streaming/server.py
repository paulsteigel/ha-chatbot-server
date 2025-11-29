from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import requests

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
    """Stream audio từ YouTube video với proper headers"""
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
            
            # Lấy headers từ yt-dlp
            headers = {}
            if 'http_headers' in info:
                headers = info['http_headers']
            
            # Stream audio với proper headers
            def generate():
                try:
                    response = requests.get(audio_url, headers=headers, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                except Exception as e:
                    print(f"Stream error: {e}")
                    
            # Xác định content type
            content_type = 'audio/webm'  # Default for YouTube
            if info.get('ext') == 'mp3':
                content_type = 'audio/mpeg'
            elif info.get('ext') in ['m4a', 'mp4']:
                content_type = 'audio/mp4'
            
            response = Response(generate(), mimetype=content_type)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            
            return response
    
    except Exception as e:
        print(f"Error in stream_audio: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
