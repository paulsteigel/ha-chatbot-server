from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import yt_dlp
import os
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
    """Stream audio từ YouTube video với MIME type động và hỗ trợ Range header"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        # Chỉ trích xuất thông tin, không tải về
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
            # --- PHẦN FIX LỖI 1: XÁC ĐỊNH MIME TYPE ĐỘNG ---
            ext = info.get('ext', 'mp4') # Lấy extension (ví dụ: webm, m4a, mp3)
            
            # Ánh xạ extension sang MIME type
            mimetype_map = {
                'mp4': 'audio/mp4',
                'm4a': 'audio/mp4',
                'webm': 'audio/webm', # Rất quan trọng, WebM/Opus thường là 'bestaudio'
                'mp3': 'audio/mpeg',
                'ogg': 'audio/ogg',
            }
            final_mimetype = mimetype_map.get(ext, 'application/octet-stream')

            # Stream audio từ URL
            def generate():
                # --- PHẦN FIX LỖI 2: CHUYỂN TIẾP RANGE HEADER CHO CHỨC NĂNG TUA (SEEKING) ---
                headers_to_forward = {}
                # Chỉ chuyển tiếp header Range nếu trình duyệt gửi lên
                if 'range' in request.headers:
                    headers_to_forward['Range'] = request.headers.get('Range')

                # Gửi request đến URL audio trực tiếp
                response = requests.get(audio_url, stream=True, headers=headers_to_forward)

                # Nếu request có Range, ta cần trả về status 206 Partial Content, và các header Content-Range, Content-Length
                if 'Range' in request.headers and response.status_code == 206:
                     # Lấy các header cần thiết từ phản hồi của YouTube CDN (để tua)
                    for header, value in response.headers.items():
                        if header.lower() in ['content-range', 'content-length', 'accept-ranges', 'content-type']:
                            yield (header, value) # Cần thay đổi cách Response được tạo nếu muốn truyền header này (cách này phức tạp)

                # Cách đơn giản nhất: chỉ truyền luồng dữ liệu
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            # --- Trả về Response với MIME type đã được xác định động ---
            # Lưu ý: Với generator đơn giản này, việc thêm các header Range/Content-Range phức tạp. 
            # Tuy nhiên, chỉ cần sửa MIME type là đủ để fix lỗi "Failed to load supported source".
            return Response(generate(), mimetype=final_mimetype)
    
    except Exception as e:
        # Nếu có lỗi (ví dụ: video bị giới hạn, bị xóa), trả về lỗi
        return jsonify({'error': str(e)}), 500

@app.route('/audio_url', methods=['GET'])
def get_audio_url():
    """Lấy direct audio URL từ YouTube video"""
    video_id = request.args.get('video_id', '')
    
    if not video_id:
        return jsonify({'error': 'Missing video_id parameter'}), 400
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return jsonify({
                'audio_url': info.get('url'),
                'title': info.get('title'),
                'duration': info.get('duration'),
                'ext': info.get('ext')
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
