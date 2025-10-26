#!/usr/bin/env python3
import os
import json
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
import tempfile
from filters import ContentFilter
from prompts import get_system_prompt

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL = os.getenv('MODEL', 'gpt-4o-mini')
PORT = int(os.getenv('LISTENING_PORT', 5000))
LANGUAGE = os.getenv('LANGUAGE', 'vi')
TTS_VOICE = os.getenv('TTS_VOICE', 'nova')
ENABLE_FILTER = os.getenv('ENABLE_WORD_FILTER', 'true').lower() == 'true'
ENABLE_EDU = os.getenv('ENABLE_EDUCATIONAL_MODE', 'true').lower() == 'true'
POLITENESS = os.getenv('POLITENESS_LEVEL', 'high')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info').upper()

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
CORS(app)

# Initialize OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Content Filter
content_filter = ContentFilter(enable=ENABLE_FILTER)

# Conversation history (in-memory, per session)
conversations = {}


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Kids Chatbot Server',
        'version': '1.0.0'
    }), 200


@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """
    Main chat endpoint for ESP32
    Accepts: audio file or text
    Returns: audio response
    """
    try:
        session_id = request.form.get('session_id', 'default')
        
        # Initialize conversation history
        if session_id not in conversations:
            conversations[session_id] = []
        
        # Handle audio input
        if 'audio' in request.files:
            audio_file = request.files['audio']
            
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                audio_file.save(temp_audio.name)
                temp_audio_path = temp_audio.name
            
            # Speech-to-Text
            logger.info(f"Processing audio from session: {session_id}")
            with open(temp_audio_path, 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    language=LANGUAGE
                )
            
            user_text = transcript.text
            os.unlink(temp_audio_path)
            
        # Handle text input
        elif 'text' in request.form:
            user_text = request.form['text']
        else:
            return jsonify({'error': 'No audio or text provided'}), 400
        
        logger.info(f"User input: {user_text}")
        
        # Check for inappropriate content
        if ENABLE_FILTER:
            filtered_result = content_filter.check_and_filter(user_text)
            if filtered_result['contains_bad_words']:
                logger.warning(f"Inappropriate content detected: {filtered_result['found_words']}")
                response_text = content_filter.get_educational_response(
                    filtered_result['found_words'],
                    politeness_level=POLITENESS
                )
                # Generate audio response
                response_audio_path = text_to_speech(response_text)
                return send_file(response_audio_path, mimetype='audio/mpeg')
        
        # Add to conversation history
        conversations[session_id].append({
            'role': 'user',
            'content': user_text
        })
        
        # Keep only last 10 messages
        if len(conversations[session_id]) > 20:
            conversations[session_id] = conversations[session_id][-20:]
        
        # Get AI response
        system_prompt = get_system_prompt(
            language=LANGUAGE,
            educational_mode=ENABLE_EDU,
            politeness_level=POLITENESS
        )
        
        messages = [{'role': 'system', 'content': system_prompt}] + conversations[session_id]
        
        logger.info("Requesting OpenAI chat completion...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_text = response.choices[0].message.content
        logger.info(f"AI response: {assistant_text}")
        
        # Add to conversation history
        conversations[session_id].append({
            'role': 'assistant',
            'content': assistant_text
        })
        
        # Convert to speech
        response_audio_path = text_to_speech(assistant_text)
        
        return send_file(
            response_audio_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='response.mp3'
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def text_to_speech(text):
    """Convert text to speech using OpenAI TTS"""
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=text
        )
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name
        
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        raise


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset conversation history for a session"""
    session_id = request.json.get('session_id', 'default')
    if session_id in conversations:
        conversations[session_id] = []
    return jsonify({'status': 'reset', 'session_id': session_id})


if __name__ == '__main__':
    logger.info(f"Starting server on port {PORT}")
    logger.info(f"Educational mode: {ENABLE_EDU}")
    logger.info(f"Content filter: {ENABLE_FILTER}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
