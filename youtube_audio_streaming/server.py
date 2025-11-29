from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import os
import requests
import re

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
    """Stream audio từ YouTube video"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,  # Enable to see debug info
        'no_warnings': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
            print(f"Audio URL: {audio_url}")
            print(f"Format: {info.get('ext')}")
            print(f"Duration: {info.get('duration')}")
            
            # Get proper mimetype
            ext = info.get('ext', 'm4a')
            mime_type = get_mime_type(ext)
            
            # Stream audio với headers phù hợp
            def generate():
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Encoding': 'identity',
                    'Range': 'bytes=0-'
                }
                
                try:
                    response = requests.get(audio_url, headers=headers, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    content_length = response.headers.get('Content-Length')
                    print(f"Content-Length: {content_length}")
                    print(f"Status Code: {response.status_code}")
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                            
                except Exception as e:
                    print(f"Stream error: {e}")
                    yield b''
            
            return Response(
                generate(),
                mimetype=mime_type,
                headers={
                    'Content-Type': mime_type,
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                    'Access-Control-Allow-Origin': '*',
                    'Accept-Ranges': 'bytes'
                }
            )
    
    except Exception as e:
        print(f"Error in stream_audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/audio_info', methods=['GET'])
def get_audio_info():
    """Lấy thông tin audio từ YouTube video"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,
        'no_warnings': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            ext = info.get('ext', 'm4a')
            mime_type = get_mime_type(ext)
            
            return jsonify({
                'audio_url': f'/stream?video_id={video_id}',
                'direct_url': info.get('url'),  # For debugging
                'title': info.get('title'),
                'duration': info.get('duration'),
                'ext': ext,
                'mime_type': mime_type,
                'format': info.get('format')
            })
    
    except Exception as e:
        print(f"Error in get_audio_info: {e}")
        return jsonify({'error': str(e)}), 500

def get_mime_type(ext):
    """Get proper mimetype for audio extension"""
    mime_map = {
        'mp3': 'audio/mpeg',
        'm4a': 'audio/mp4',
        'aac': 'audio/aac',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
        'webm': 'audio/webm'
    }
    return mime_map.get(ext.lower(), 'audio/mpeg')

# Alternative endpoint that returns direct URL for testing
@app.route('/direct_url', methods=['GET'])
def get_direct_url():
    """Get direct audio URL for testing"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,
        'no_warnings': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return jsonify({
                'direct_url': info.get('url'),
                'title': info.get('title'),
                'ext': info.get('ext'),
                'format': info.get('format_id')
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)