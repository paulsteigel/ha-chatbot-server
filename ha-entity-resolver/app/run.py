#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HA Entity Resolver for ESP32 MCP Bot
Version: 1.0.1 - Auto MQTT topic detection
"""

import os
import json
import logging
import sys
import requests
from flask import Flask, jsonify, request, g
from functools import wraps
from rapidfuzz import fuzz

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================
# Configuration
# ============================================
HA_URL = os.environ.get('HA_URL', 'http://supervisor/core')
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
MQTT_PREFIX = ''
ACCESS_TOKENS = []

def load_config():
    """Load configuration from temporary files"""
    global ACCESS_TOKENS, MQTT_PREFIX
    
    try:
        with open('/tmp/access_tokens.json', 'r') as f:
            ACCESS_TOKENS = json.load(f)
            logger.info(f"Loaded {len(ACCESS_TOKENS)} access tokens")
    except Exception as e:
        logger.warning(f"Could not load access tokens: {e}")
    
    try:
        with open('/tmp/mqtt_prefix.txt', 'r') as f:
            MQTT_PREFIX = f.read().strip()
            logger.info(f"MQTT device prefix: {MQTT_PREFIX}")
    except:
        MQTT_PREFIX = "192168100131"
        logger.info(f"Using default MQTT prefix: {MQTT_PREFIX}")

load_config()

# ============================================
# Authentication
# ============================================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        
        if not auth:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        token_config = next((t for t in ACCESS_TOKENS if t.get('token') == auth), None)
        if not token_config:
            logger.warning(f"Invalid token from {request.remote_addr}")
            return jsonify({"error": "Invalid token"}), 403
        
        g.token_name = token_config.get('name', 'Unknown')
        return f(*args, **kwargs)
    
    return decorated

# ============================================
# HA API Helper
# ============================================
def call_ha_api(endpoint):
    """Call Home Assistant API"""
    url = f"{HA_URL}/api/{endpoint}"
    headers = {
        'Authorization': f'Bearer {SUPERVISOR_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"HA API error ({endpoint}): {e}")
        return None

def get_mqtt_topic_from_entity(entity_id):
    """
    Tự động lấy MQTT topic từ HA entity
    Ưu tiên: MQTT attributes > ESPHome discovery > Auto-generate
    """
    # 1. Lấy state của entity
    states = call_ha_api('states')
    if not states:
        return auto_generate_topic(entity_id)
    
    entity_state = next((s for s in states if s['entity_id'] == entity_id), None)
    if not entity_state:
        return auto_generate_topic(entity_id)
    
    attrs = entity_state.get('attributes', {})
    
    # 2. Check MQTT discovery attributes (ESPHome devices)
    # ESPHome publishes: {device_id}/{domain}/{object_id}
    if 'friendly_name' in attrs:
        # Try to find MQTT topic from integration
        domain, object_id = entity_id.split('.')
        
        # ESPHome standard format
        base_topic = f"{MQTT_PREFIX}/{domain}/{object_id}"
        return {
            'command': f"{base_topic}/command",
            'state': f"{base_topic}/state"
        }
    
    # 3. Fallback to auto-generate
    return auto_generate_topic(entity_id)

def auto_generate_topic(entity_id):
    """Auto-generate MQTT topic"""
    domain, object_id = entity_id.split('.')
    base = f"{MQTT_PREFIX}/{domain}/{object_id}"
    return {
        'command': f"{base}/command",
        'state': f"{base}/state"
    }

# ============================================
# API Routes
# ============================================
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "addon": "HA Entity Resolver for ESP32 MCP Bot",
        "version": "1.0.1",
        "endpoints": {
            "GET /health": "Health check",
            "POST /api/resolve": "Resolve entity name to MQTT topic",
            "GET /api/entities/minimal": "Get minimal entity list"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "version": "1.0.1",
        "ha_connected": SUPERVISOR_TOKEN != ''
    })

@app.route('/api/resolve', methods=['POST'])
@token_required
def resolve_entity():
    """
    Resolve fuzzy entity name to MQTT topic
    
    Request: {"query": "đèn phòng khách"}
    Response: {
        "entity_id": "switch.den_phong_khach",
        "friendly_name": "Đèn Phòng Khách",
        "command_topic": "192168100131/switch/den_phong_khach/command",
        "state_topic": "192168100131/switch/den_phong_khach/state",
        "current_state": "off",
        "confidence": 95
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    
    query = data.get('query', '').lower().strip()
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400
    
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities from HA"}), 500
    
    # Fuzzy search
    candidates = []
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        if domain not in ['switch', 'light', 'fan', 'cover', 'climate']:
            continue
        
        friendly_name = state.get('attributes', {}).get('friendly_name', entity_id)
        search_text = f"{friendly_name} {entity_id}".lower()
        
        score = fuzz.partial_ratio(query, search_text)
        
        if score >= 60:
            candidates.append({
                "entity_id": entity_id,
                "friendly_name": friendly_name,
                "state": state.get('state', 'unknown'),
                "score": score
            })
    
    if not candidates:
        logger.warning(f"[{g.token_name}] No match for query: '{query}'")
        return jsonify({
            "error": "No matching entity found",
            "query": query
        }), 404
    
    candidates.sort(key=lambda x: x['score'], reverse=True)
    best = candidates[0]
    
    topics = get_mqtt_topic_from_entity(best['entity_id'])
    
    logger.info(f"[{g.token_name}] Resolved '{query}' → {best['entity_id']} (confidence: {best['score']}%)")
    
    return jsonify({
        "entity_id": best['entity_id'],
        "friendly_name": best['friendly_name'],
        "command_topic": topics['command'],
        "state_topic": topics['state'],
        "current_state": best['state'],
        "confidence": best['score']
    })

@app.route('/api/entities/minimal', methods=['GET'])
@token_required
def get_minimal_entities():
    """Get minimal entity list for ESP32 caching"""
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities"}), 500
    
    result = []
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        if domain not in ['switch', 'light', 'fan', 'cover', 'climate']:
            continue
        
        topics = get_mqtt_topic_from_entity(entity_id)
        friendly_name = state.get('attributes', {}).get('friendly_name', entity_id)
        
        result.append({
            "id": entity_id,
            "n": friendly_name[:30],
            "ct": topics['command'],
            "st": topics['state']
        })
    
    logger.info(f"[{g.token_name}] Returned {len(result)} minimal entities")
    
    return jsonify({
        "count": len(result),
        "entities": result
    })

# ============================================
# Main
# ============================================
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("HA Entity Resolver Starting")
    logger.info(f"  Version: 1.0.1")
    logger.info(f"  HA URL: {HA_URL}")
    logger.info(f"  MQTT Prefix: {MQTT_PREFIX}")
    logger.info(f"  Configured tokens: {len(ACCESS_TOKENS)}")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)
