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
    """
    Stream audio từ YouTube video.
    Hỗ trợ Range Request (206 Partial Content) để trình duyệt không báo lỗi.
    """
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # 1. Lấy URL thực của file audio từ YouTube
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        audio_url = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']

        if not audio_url:
            return jsonify({'error': 'Cannot extract audio url'}), 404

        # 2. Chuẩn bị Headers để gửi request đến YouTube Server
        # Quan trọng: Phải lấy Range header TỪ TRƯỚC khi vào hàm generate
        headers = {}
        if 'Range' in request.headers:
            headers['Range'] = request.headers['Range']
        
        # User-Agent giả lập để tránh bị chặn
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

        # 3. Gọi request đến YouTube server (Proxy stream)
        # stream=True là bắt buộc để không tải toàn bộ file về RAM
        upstream_response = requests.get(audio_url, headers=headers, stream=True)

        # 4. Chuẩn bị Headers trả về cho trình duyệt (Client)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers_response = [
            (name, value) for (name, value) in upstream_response.headers.items()
            if name.lower() not in excluded_headers
        ]
        
        # Thêm các header quan trọng thủ công để đảm bảo tính chính xác
        if 'Content-Length' in upstream_response.headers:
            headers_response.append(('Content-Length', upstream_response.headers['Content-Length']))
        
        if 'Content-Range' in upstream_response.headers:
            headers_response.append(('Content-Range', upstream_response.headers['Content-Range']))
            
        # Đảm bảo Content-Type đúng (thường là audio/webm hoặc audio/mp4)
        content_type = upstream_response.headers.get('Content-Type', 'audio/mp4')
        
        # 5. Hàm Generator để đẩy dữ liệu
        def generate():
            try:
                for chunk in upstream_response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except Exception as e:
                print(f"Stream error: {e}")

        # 6. Trả về Response
        # Status Code: 206 (Partial) nếu có Range, hoặc 200 (OK) nếu tải từ đầu
        return Response(
            generate(),
            status=upstream_response.status_code,
            mimetype=content_type,
            headers=headers_response,
            direct_passthrough=True
        )

    except Exception as e:
        print(f"Error processing stream: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Threaded=True là cần thiết để xử lý nhiều request đồng thời (vừa tải trang vừa stream)
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)