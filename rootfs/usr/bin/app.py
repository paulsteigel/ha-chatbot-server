#!/usr/bin/env python3
import os
import sys
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime
import json

# Add utils to path
sys.path.insert(0, '/usr/bin')
from utils import ContentFilter, ResponseTemplates

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== CONFIG ====================
logger.info("=" * 50)
logger.info("  Kids ChatBot Server v1.0.3")
logger.info("=" * 50)

options = {}
config_path = '/data/options.json'

if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        options = json.load(f)

OPENAI_API_KEY = options.get('openai_api_key', os.getenv('OPENAI_API_KEY'))
LANGUAGE = options.get('language', 'vi')
VOICE = options.get('voice', 'nova')
PERSONALITY = options.get('personality', 'gentle_teacher')
CONTENT_FILTER = options.get('content_filter', True)
PORT = options.get('port', 5000)

logger.info(f"Port: {PORT}")
logger.info(f"Language: {LANGUAGE}")
logger.info(f"Voice: {VOICE}")
logger.info(f"Personality: {PERSONALITY}")
logger.info(f"Content Filter: {'Enabled' if CONTENT_FILTER else 'Disabled'}")

if OPENAI_API_KEY:
    logger.info(f"API Key: {OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:]} ✓")
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.error("API Key: NOT CONFIGURED ✗")
    client = None

# ==================== FLASK APP ====================
app = Flask(__name__)
CORS(app)

sessions = {}

SYSTEM_PROMPTS = {
    'gentle_teacher': """Bạn là giáo viên tiếng Việt vui vẻ, kiên nhẫn, thân thiện với trẻ em.
    Trả lời đơn giản, dễ hiểu, khuyến khích học hỏi. An toàn và phù hợp với trẻ em.""",
    'friend': """Bạn là người bạn thân thiện với trẻ em. Vui vẻ, hữu ích, an toàn.""",
    'storyteller': """Bạn là người kể chuyện tài ba. Sáng tạo, giáo dục, an toàn cho trẻ."""
}

@app.route('/')
def index():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kids ChatBot Server</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
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
            max-width: 600px;
            width: 100%;
        }
        h1 { color: #667eea; text-align: center; margin-bottom: 30px; }
        .status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .status.ok { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover { background: #5568d3; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Kids ChatBot Server</h1>
        <div id="status" class="status">⏳ Checking...</div>
        <button onclick="testHealth()">🧪 Test Health</button>
        <button onclick="testChat()">💬 Test Chat</button>
        <div id="result"></div>
    </div>
    <script>
        async function checkStatus() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                document.getElementById('status').className = 'status ok';
                document.getElementById('status').innerText = '✅ Server Online - v' + data.version;
            } catch (e) {
                document.getElementById('status').className = 'status error';
                document.getElementById('status').innerText = '❌ Server Offline';
            }
        }
        
        async function testHealth() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            } catch (e) {
                document.getElementById('result').innerHTML = '<pre>Error: ' + e.message + '</pre>';
            }
        }
        
        async function testChat() {
            try {
                const res = await fetch('/text-chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: 'Xin chào!', session_id: 'test_' + Date.now()})
                });
                const data = await res.json();
                document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            } catch (e) {
                document.getElementById('result').innerHTML = '<pre>Error: ' + e.message + '</pre>';
            }
        }
        
        checkStatus();
        setInterval(checkStatus, 30000);
    </script>
</body>
</html>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'version': '1.0.3',
        'timestamp': datetime.now().isoformat(),
        'api_configured': bool(client),
        'content_filter': CONTENT_FILTER
    })

@app.route('/text-chat', methods=['POST'])
def text_chat():
    try:
        if not client:
            return jsonify({'error': ResponseTemplates.get_error('no_api_key')}), 500
        
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not message:
            return jsonify({'error': ResponseTemplates.get_error('empty_message')}), 400
        
        # Content filter check
        if CONTENT_FILTER and not ContentFilter.is_safe(message):
            return jsonify({
                'response': ContentFilter.sanitize(message),
                'session_id': session_id,
                'filtered': True
            })
        
        logger.info(f"[{session_id}] User: {message}")
        
        if session_id not in sessions:
            sessions[session_id] = []
        
        sessions[session_id].append({'role': 'user', 'content': message})
        
        system_prompt = SYSTEM_PROMPTS.get(PERSONALITY, SYSTEM_PROMPTS['gentle_teacher'])
        messages = [{'role': 'system', 'content': system_prompt}] + sessions[session_id][-10:]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        reply = response.choices[0].message.content
        
        # Filter AI response too
        if CONTENT_FILTER and not ContentFilter.is_safe(reply):
            reply = ContentFilter.sanitize(reply)
        
        logger.info(f"[{session_id}] AI: {reply}")
        
        sessions[session_id].append({'role': 'assistant', 'content': reply})
        
        return jsonify({
            'response': reply,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'filtered': False
        })
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': ResponseTemplates.get_error('api_error')}), 500

@app.route('/config')
def get_config():
    return jsonify({
        'language': LANGUAGE,
        'voice': VOICE,
        'personality': PERSONALITY,
        'content_filter': CONTENT_FILTER,
        'api_configured': bool(client)
    })

if __name__ == '__main__':
    logger.info(f"Starting Flask server on port {PORT}...")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=PORT, debug=False)
