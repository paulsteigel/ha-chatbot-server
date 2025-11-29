from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import requests
import logging

# Cấu hình log để thấy lỗi rõ hơn trong console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='www', static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('www', 'index.html')

@app.route('/search', methods=['GET'])
def search_youtube():
    query = request.args.get('q', '')
    max_results = int(request.args.get('max_results', 10))
    
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_ipv4': True, # Ép dùng IPv4 để tránh lỗi network docker
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
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream', methods=['GET'])
def stream_audio():
    video_id = request.args.get('video_id', '')
    logger.info(f"Received stream request for Video ID: {video_id}")
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best', 
        'quiet': True,
        'no_warnings': True,
        'force_ipv4': True, # Quan trọng cho môi trường Home Assistant/Docker
        'noplaylist': True,
    }
    
    try:
        audio_url = None
        content_type = 'audio/mp4' # Default

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Tải thông tin video
            info = ydl.extract_info(video_url, download=False)
            
            # CÁCH 1: Thử lấy URL trực tiếp
            if 'url' in info:
                audio_url = info['url']
                logger.info("Found URL via direct method")
            
            # CÁCH 2: Nếu cách 1 thất bại, tự lọc trong danh sách formats
            if not audio_url and 'formats' in info:
                logger.info("Direct URL not found, searching in formats...")
                formats = info.get('formats', [])
                # Lọc ra các file chỉ có audio (vcodec='none')
                audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
                
                # Sắp xếp theo bitrate (tbr) giảm dần để lấy chất lượng tốt nhất
                if audio_formats:
                    audio_formats.sort(key=lambda x: x.get('tbr', 0) or 0, reverse=True)
                    best_audio = audio_formats[0]
                    audio_url = best_audio.get('url')
                    logger.info(f"Found audio URL via formats scan. ID: {best_audio.get('format_id')}")
            
        if not audio_url:
            logger.error("Failed to extract ANY audio URL from yt-dlp")
            return jsonify({'error': 'Cannot extract audio url from YouTube'}), 404

        # Chuẩn bị request đến server Google
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        if 'Range' in request.headers:
            headers['Range'] = request.headers['Range']
            logger.info(f"Forwarding Range header: {headers['Range']}")

        # Thực hiện request (Proxy)
        upstream_response = requests.get(audio_url, headers=headers, stream=True, timeout=10)
        
        # Nếu link google trả về 403 (Forbidden) -> Link hết hạn hoặc bị chặn IP
        if upstream_response.status_code == 403:
            logger.error("YouTube returned 403 Forbidden. IP might be blocked or URL expired.")
            return jsonify({'error': 'YouTube refused connection (403)'}), 403

        # Lọc headers trả về
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers_response = [
            (name, value) for (name, value) in upstream_response.headers.items()
            if name.lower() not in excluded_headers
        ]
        
        # Thêm lại các header quan trọng
        if 'Content-Length' in upstream_response.headers:
            headers_response.append(('Content-Length', upstream_response.headers['Content-Length']))
        if 'Content-Range' in upstream_response.headers:
            headers_response.append(('Content-Range', upstream_response.headers['Content-Range']))
            
        content_type = upstream_response.headers.get('Content-Type', 'audio/mp4')

        def generate():
            try:
                for chunk in upstream_response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except Exception as e:
                logger.error(f"Stream broken: {e}")

        logger.info(f"Streaming started. Status: {upstream_response.status_code}, Type: {content_type}")
        
        return Response(
            generate(),
            status=upstream_response.status_code,
            mimetype=content_type,
            headers=headers_response,
            direct_passthrough=True
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in stream: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Threaded=True là bắt buộc
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)