#!/usr/bin/env python3
import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime
import json
import tempfile

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
logger.info("=" * 50)
logger.info("  Kids ChatBot Server Starting")
logger.info("=" * 50)

# Load config từ Home Assistant
options = {}
config_path = '/data/options.json'
if os.path.exists(config_path):
    logger.info("Creating configuration file...")
    with open(config_path, 'r') as f:
        options = json.load(f)

# Config
OPENAI_API_KEY = options.get('openai_api_key', os.getenv('OPENAI_API_KEY'))
LANGUAGE = options.get('language', 'vi')
VOICE = options.get('voice', 'nova')
PERSONALITY = options.get('personality', 'gentle_teacher')
CONTENT_FILTER = options.get('content_filter', True)
EDUCATIONAL_MODE = options.get('educational_mode', True)
LOG_LEVEL = options.get('log_level', 'info')
PORT = options.get('port', 5000)

logger.info("-" * 40)
logger.info("Configuration loaded:")
logger.info(f"  Port: {PORT}")
logger.info(f"  Language: {LANGUAGE}")
logger.info(f"  Voice: {VOICE}")
logger.info(f"  Personality: {PERSONALITY}")
logger.info(f"  Content Filter: {CONTENT_FILTER}")
logger.info(f"  Educational Mode: {EDUCATIONAL_MODE}")
logger.info(f"  Log Level: {LOG_LEVEL}")
if OPENAI_API_KEY:
    logger.info(f"  API Key: {OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:]} ✓")
else:
    logger.error("  API Key: NOT CONFIGURED ✗")
logger.info("-" * 40)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ==================== FLASK APP ====================
app = Flask(__name__)
CORS(app)

# Session storage
sessions = {}

# System prompts based on personality
SYSTEM_PROMPTS = {
    'gentle_teacher': """Bạn là một giáo viên tiếng Việt vui vẻ, kiên nhẫn và thân thiện đang nói chuyện với trẻ em. 
    Hãy trả lời bằng tiếng Việt, giải thích đơn giản, dễ hiểu, và khuyến khích học hỏi.
    Luôn an toàn, phù hợp với trẻ em, và giáo dục.""",
    
    'friend': """Bạn là một người bạn thân thiện đang trò chuyện với trẻ em bằng tiếng Việt.
    Hãy vui vẻ, hữu ích và luôn an toàn cho trẻ em.""",
    
    'storyteller': """Bạn là một người kể chuyện tài ba, kể những câu chuyện thú vị và bài học giáo dục bằng tiếng Việt cho trẻ em.
    Hãy sáng tạo, an toàn và phù hợp với lứa tuổi."""
}

# ==================== WEB INTERFACE ====================
@app.route('/')
def index():
    """Main web interface"""
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kids ChatBot - Voice Assistant</title>
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
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 800px;
            width: 100%;
        }
        h1 { color: #667eea; text-align: center; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; }
        .status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            font-weight: bold;
        }
        .status.connected { background: #d4edda; color: #155724; }
        .status.disconnected { background: #f8d7da; color: #721c24; }
        .endpoint {
            background: #f8f9fa;
            padding: 20px;
            margin: 15px 0;
            border-left: 4px solid #667eea;
            border-radius: 8px;
        }
        .endpoint h3 { color: #667eea; margin-bottom: 10px; font-size: 16px; }
        .endpoint p { color: #666; margin-bottom: 10px; }
        .endpoint code {
            background: #e9ecef;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            margin-top: 10px;
            font-size: 14px;
            transition: all 0.3s;
        }
        button:hover { background: #5568d3; transform: translateY(-2px); }
        #testResult {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            display: none;
        }
        pre {
            background: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
        }
        .info-box {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-top: 20px;
            border-radius: 8px;
        }
        .info-box h3 { color: #2196F3; margin-bottom: 10px; font-size: 16px; }
        .info-box ul { margin-left: 20px; }
        .info-box li { margin: 5px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Kids ChatBot API</h1>
        <p class="subtitle">Voice Assistant Server</p>
        
        <div id="status" class="status disconnected">🔴 Đang kiểm tra...</div>

        <div class="endpoint">
            <h3>GET /health</h3>
            <p>Health check endpoint</p>
            <button onclick="testHealth()">🧪 Test</button>
        </div>

        <div class="endpoint">
            <h3>POST /chat</h3>
            <p>Voice chat - Upload audio file, receive audio response</p>
            <code>Content-Type: multipart/form-data</code>
        </div>

        <div class="endpoint">
            <h3>POST /text-chat</h3>
            <p>Text chat - Send text message, receive text response</p>
            <code>{"message": "Xin chào", "session_id": "test123"}</code>
            <button onclick="testTextChat()">🧪 Test</button>
        </div>

        <div class="endpoint">
            <h3>GET /config</h3>
            <p>Get current configuration</p>
            <button onclick="testConfig()">🧪 Test</button>
        </div>

        <div id="testResult"></div>

        <div class="info-box">
            <h3>📖 Thông tin:</h3>
            <ul>
                <li><strong>Version:</strong> 1.0.3</li>
                <li><strong>Language:</strong> Vietnamese (vi)</li>
                <li><strong>Voice:</strong> Nova (Female)</li>
                <li><strong>Domain:</strong> school.sfdp.net</li>
                <li><strong>Port:</strong> 5000</li>
            </ul>
        </div>
    </div>

    <script>
        async function checkHealth() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                document.getElementById('status').className = 'status connected';
                document.getElementById('status').innerHTML = '🟢 Server hoạt động - v' + data.version;
            } catch (error) {
                document.getElementById('status').className = 'status disconnected';
                document.getElementById('status').innerHTML = '🔴 Không kết nối được';
            }
        }

        async function testHealth() {
            showResult('⏳ Testing /health...');
            try {
                const response = await fetch('/health');
                const data = await response.json();
                showResult('✅ Success!', data, '#d4edda');
            } catch (error) {
                showResult('❌ Error: ' + error.message, null, '#f8d7da');
            }
        }

        async function testTextChat() {
            showResult('⏳ Testing /text-chat...');
            try {
                const response = await fetch('/text-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: 'Xin chào!',
                        session_id: 'web_test_' + Date.now()
                    })
                });
                const data = await response.json();
                showResult('✅ Success!', data, '#d4edda');
            } catch (error) {
                showResult('❌ Error: ' + error.message, null, '#f8d7da');
            }
        }

        async function testConfig() {
            showResult('⏳ Testing /config...');
            try {
                const response = await fetch('/config');
                const data = await response.json();
                showResult('✅ Success!', data, '#d4edda');
            } catch (error) {
                showResult('❌ Error: ' + error.message, null, '#f8d7da');
            }
        }

        function showResult(message, data = null, bgColor = '#f8f9fa') {
            const result = document.getElementById('testResult');
            result.style.display = 'block';
            result.style.background = bgColor;
            result.innerHTML = '<strong>' + message + '</strong>';
            if (data) {
                result.innerHTML += '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            }
        }

        window.addEventListener('load', checkHealth);
        setInterval(checkHealth, 30000);
    </script>
</body>
</html>
    """

@app.route('/favicon.ico')
def favicon():
    """Favicon"""
    return '', 204

# ==================== API ENDPOINTS ====================
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.3'
    }), 200

@app.route('/chat', methods=['POST'])
def voice_chat():
    """Voice chat endpoint - receives audio, returns audio"""
    try:
        if not client:
            return jsonify({'error': 'OpenAI API not configured'}), 500

        # Get audio file from request
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        session_id = request.form.get('session_id', 'default')

        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            audio_file.save(temp_audio.name)
            temp_audio_path = temp_audio.name

        # Transcribe audio
        with open(temp_audio_path, 'rb') as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                language=LANGUAGE
            )
        
        user_message = transcript.text
        logger.info(f"[{session_id}] User: {user_message}")

        # Get or create session
        if session_id not in sessions:
            sessions[session_id] = []

        # Add user message to history
        sessions[session_id].append({
            'role': 'user',
            'content': user_message
        })

        # Get AI response
        system_prompt = SYSTEM_PROMPTS.get(PERSONALITY, SYSTEM_PROMPTS['gentle_teacher'])
        messages = [{'role': 'system', 'content': system_prompt}] + sessions[session_id][-10:]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        ai_message = response.choices[0].message.content
        logger.info(f"[{session_id}] AI: {ai_message}")

        # Add AI response to history
        sessions[session_id].append({
            'role': 'assistant',
            'content': ai_message
        })

        # Convert to speech
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=ai_message
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_speech:
            temp_speech.write(speech_response.content)
            temp_speech_path = temp_speech.name

        # Clean up input audio
        os.unlink(temp_audio_path)

        # Return audio file
        return send_file(
            temp_speech_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='response.mp3'
        )

    except Exception as e:
        logger.error(f"Error in voice chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/text-chat', methods=['POST'])
def text_chat():
    """Text chat endpoint"""
    try:
        if not client:
            return jsonify({'error': 'OpenAI API not configured'}), 500

        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id', 'default')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        logger.info(f"[{session_id}] User: {user_message}")

        # Get or create session
        if session_id not in sessions:
            sessions[session_id] = []

        # Add user message
        sessions[session_id].append({
            'role': 'user',
            'content': user_message
        })

        # Get AI response
        system_prompt = SYSTEM_PROMPTS.get(PERSONALITY, SYSTEM_PROMPTS['gentle_teacher'])
        messages = [{'role': 'system', 'content': system_prompt}] + sessions[session_id][-10:]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        ai_message = response.choices[0].message.content
        logger.info(f"[{session_id}] AI: {ai_message}")

        # Add AI response
        sessions[session_id].append({
            'role': 'assistant',
            'content': ai_message
        })

        return jsonify({
            'response': ai_message,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error in text chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'language': LANGUAGE,
        'voice': VOICE,
        'personality': PERSONALITY,
        'content_filter': CONTENT_FILTER,
        'educational_mode': EDUCATIONAL_MODE,
        'api_configured': bool(client)
    }), 200

# ==================== MAIN ====================
if __name__ == '__main__':
    logger.info(f"Starting Flask server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
