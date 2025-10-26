#!/usr/bin/env python3
"""
Kids ChatBot Server - OpenAI Voice Chat for Home Assistant
Author: Đặng Đình Ngọc <ngocdd@sfdp.net>
"""

import os
import io
import logging
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from openai import OpenAI
from utils.content_filter import ContentFilter
from utils.response_templates import ResponseTemplates

# Configuration
PORT = int(os.getenv('PORT', 5000))
LANGUAGE = os.getenv('LANGUAGE', 'vi')
MODEL = os.getenv('MODEL', 'gpt-4o-mini')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', 500))
TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
VOICE = os.getenv('VOICE', 'nova')
CONTENT_FILTER_ENABLED = os.getenv('CONTENT_FILTER_ENABLED', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info').upper()

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize content filter and templates
content_filter = ContentFilter(language=LANGUAGE)
response_templates = ResponseTemplates(language=LANGUAGE)

# System prompt
SYSTEM_PROMPT = response_templates.get_system_prompt()

# HTML Template for Web UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kids ChatBot Test</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #667eea;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2em;
        }
        .status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .status.ready { background: #d4edda; color: #155724; }
        .status.recording { background: #fff3cd; color: #856404; }
        .status.processing { background: #cce5ff; color: #004085; }
        .status.error { background: #f8d7da; color: #721c24; }
        
        .btn-container {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }
        button {
            flex: 1;
            padding: 15px;
            font-size: 16px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
        }
        .btn-record {
            background: #28a745;
            color: white;
        }
        .btn-record:hover { background: #218838; }
        .btn-record:disabled { background: #6c757d; cursor: not-allowed; }
        
        .btn-stop {
            background: #dc3545;
            color: white;
        }
        .btn-stop:hover { background: #c82333; }
        .btn-stop:disabled { background: #6c757d; cursor: not-allowed; }
        
        .response-box {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            min-height: 100px;
            margin-top: 20px;
        }
        .response-box h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .response-text {
            color: #333;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .audio-player {
            width: 100%;
            margin-top: 15px;
        }
        .config-info {
            background: #e9ecef;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
        }
        .config-info strong { color: #667eea; }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        .recording { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Kids ChatBot Test</h1>
        
        <div id="status" class="status ready">
            ✅ Sẵn sàng - Nhấn nút để bắt đầu
        </div>
        
        <div class="btn-container">
            <button id="recordBtn" class="btn-record">
                🎤 Bắt đầu ghi âm
            </button>
            <button id="stopBtn" class="btn-stop" disabled>
                ⏹️ Dừng ghi âm
            </button>
        </div>
        
        <div class="response-box">
            <h3>📝 Phản hồi:</h3>
            <div id="responseText" class="response-text">
                Chưa có phản hồi nào...
            </div>
            <audio id="audioPlayer" class="audio-player" controls style="display:none;"></audio>
        </div>
        
        <div class="config-info">
            <strong>Cấu hình:</strong><br>
            Model: {{ model }} | Language: {{ language }} | Voice: {{ voice }}<br>
            Content Filter: {{ 'Enabled' if content_filter else 'Disabled' }}
        </div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        
        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const status = document.getElementById('status');
        const responseText = document.getElementById('responseText');
        const audioPlayer = document.getElementById('audioPlayer');
        
        recordBtn.addEventListener('click', startRecording);
        stopBtn.addEventListener('click', stopRecording);
        
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = sendAudio;
                
                mediaRecorder.start();
                
                recordBtn.disabled = true;
                stopBtn.disabled = false;
                recordBtn.classList.add('recording');
                status.className = 'status recording';
                status.textContent = '🎙️ Đang ghi âm...';
            } catch (err) {
                console.error('Error accessing microphone:', err);
                status.className = 'status error';
                status.textContent = '❌ Không thể truy cập microphone!';
            }
        }
        
        function stopRecording() {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            
            recordBtn.disabled = false;
            stopBtn.disabled = true;
            recordBtn.classList.remove('recording');
            status.className = 'status processing';
            status.textContent = '⏳ Đang xử lý...';
        }
        
        async function sendAudio() {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    responseText.textContent = data.text;
                    
                    if (data.audio_url) {
                        audioPlayer.src = data.audio_url;
                        audioPlayer.style.display = 'block';
                        audioPlayer.play();
                    }
                    
                    status.className = 'status ready';
                    status.textContent = '✅ Hoàn thành!';
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (err) {
                console.error('Error:', err);
                status.className = 'status error';
                status.textContent = '❌ Lỗi: ' + err.message;
                responseText.textContent = 'Đã xảy ra lỗi khi xử lý yêu cầu.';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Web UI for testing"""
    return render_template_string(
        HTML_TEMPLATE,
        model=MODEL,
        language=LANGUAGE,
        voice=VOICE,
        content_filter=CONTENT_FILTER_ENABLED
    )

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'version': '1.0.0'})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        # Get audio file
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Transcribe audio
        logger.info("Transcribing audio...")
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=LANGUAGE
        )
        user_text = transcription.text
        logger.info(f"User said: {user_text}")
        
        # Content filter
        if CONTENT_FILTER_ENABLED:
            is_safe, filtered_text = content_filter.filter(user_text)
            if not is_safe:
                logger.warning(f"Inappropriate content detected: {user_text}")
                response_text = response_templates.get_inappropriate_content_response()
                return generate_audio_response(response_text)
        
        # Get ChatGPT response
        logger.info("Getting ChatGPT response...")
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        response_text = completion.choices[0].message.content
        logger.info(f"ChatGPT response: {response_text}")
        
        return generate_audio_response(response_text)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_audio_response(text):
    """Generate audio from text and return response"""
    try:
        # Generate speech
        logger.info("Generating speech...")
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=text
        )
        
        # Save audio to memory
        audio_buffer = io.BytesIO()
        for chunk in speech_response.iter_bytes():
            audio_buffer.write(chunk)
        audio_buffer.seek(0)
        
        # Return JSON with audio URL
        return jsonify({
            'success': True,
            'text': text,
            'audio_url': '/api/audio/latest'
        })
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Store latest audio in memory
latest_audio = None

@app.route('/api/audio/latest')
def get_latest_audio():
    """Get the latest generated audio"""
    global latest_audio
    if latest_audio:
        return send_file(latest_audio, mimetype='audio/mpeg')
    return jsonify({'error': 'No audio available'}), 404

if __name__ == '__main__':
    logger.info(f"Starting Kids ChatBot Server on port {PORT}")
    logger.info(f"Model: {MODEL} | Language: {LANGUAGE} | Voice: {VOICE}")
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
