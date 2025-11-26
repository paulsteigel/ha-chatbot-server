#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HA Entity Resolver for ESP32 MCP Bot
Author: Đặng Đình Ngọc (ngocdd@sfdp.net)
Version: 1.0.0
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
ACCESS_TOKENS = []
ENTITY_MQTT_MAP = {}

def load_config():
    """Load configuration from files"""
    global ACCESS_TOKENS, ENTITY_MQTT_MAP
    
    # Load access tokens
    try:
        with open('/tmp/access_tokens.json', 'r') as f:
            ACCESS_TOKENS = json.load(f)
            logger.info(f"Loaded {len(ACCESS_TOKENS)} access tokens")
    except Exception as e:
        logger.warning(f"Could not load access tokens: {e}")
    
    # Load entity MQTT map
    try:
        with open('/tmp/entity_mqtt_map.json', 'r') as f:
            ENTITY_MQTT_MAP = json.load(f)
            logger.info(f"Loaded {len(ENTITY_MQTT_MAP)} entity mappings")
    except Exception as e:
        logger.info("No entity MQTT map provided, will use auto-generation")

load_config()

# ============================================
# Authentication
# ============================================
def token_required(f):
    """Authentication decorator"""
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
# Home Assistant API Helper
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

def get_mqtt_topic(entity_id):
    """
    Convert entity_id to MQTT topic
    Priority: mapping table > auto-generate
    """
    # Check mapping table
    if entity_id in ENTITY_MQTT_MAP:
        base = ENTITY_MQTT_MAP[entity_id]
        return {
            'command': f"{base}/command",
            'state': f"{base}/state"
        }
    
    # Auto-generate (ESPHome standard)
    domain, object_id = entity_id.split('.')
    base = f"192168100131/{domain}/{object_id}"
    return {
        'command': f"{base}/command",
        'state': f"{base}/state"
    }

# ============================================
# API Routes
# ============================================
@app.route('/', methods=['GET'])
def root():
    """API documentation"""
    return jsonify({
        "addon": "HA Entity Resolver for ESP32 MCP Bot",
        "version": "1.0.0",
        "author": "Đặng Đình Ngọc",
        "endpoints": {
            "GET /health": "Health check",
            "POST /api/resolve": "Resolve entity name to MQTT topic",
            "GET /api/entities/minimal": "Get minimal entity list",
            "GET /api/entities/full": "Get full entity list with states"
        },
        "authentication": "Required: Authorization: Bearer <token>"
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
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
    
    # Get all states
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities from HA"}), 500
    
    # Fuzzy search
    candidates = []
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        # Only controllable devices
        if domain not in ['switch', 'light', 'fan', 'cover', 'climate']:
            continue
        
        friendly_name = state.get('attributes', {}).get('friendly_name', entity_id)
        search_text = f"{friendly_name} {entity_id}".lower()
        
        # Calculate fuzzy score
        score = fuzz.partial_ratio(query, search_text)
        
        if score >= 60:  # Threshold
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
            "query": query,
            "hint": "Try more specific keywords"
        }), 404
    
    # Sort by score
    candidates.sort(key=lambda x: x['score'], reverse=True)
    best = candidates[0]
    
    # Get MQTT topics
    topics = get_mqtt_topic(best['entity_id'])
    
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
    """
    Get minimal entity list for ESP32 caching
    Response: [{"id": "...", "n": "...", "ct": "...", "st": "..."}, ...]
    """
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities"}), 500
    
    result = []
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        if domain not in ['switch', 'light', 'fan', 'cover', 'climate']:
            continue
        
        topics = get_mqtt_topic(entity_id)
        friendly_name = state.get('attributes', {}).get('friendly_name', entity_id)
        
        result.append({
            "id": entity_id,
            "n": friendly_name[:30],  # Truncate for ESP32 memory
            "ct": topics['command'],
            "st": topics['state']
        })
    
    logger.info(f"[{g.token_name}] Returned {len(result)} minimal entities")
    
    return jsonify({
        "count": len(result),
        "entities": result
    })

@app.route('/api/entities/full', methods=['GET'])
@token_required
def get_full_entities():
    """Get full entity list with current states"""
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities"}), 500
    
    result = []
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        if domain not in ['switch', 'light', 'fan', 'cover', 'climate']:
            continue
        
        topics = get_mqtt_topic(entity_id)
        
        result.append({
            "entity_id": entity_id,
            "friendly_name": state.get('attributes', {}).get('friendly_name', entity_id),
            "domain": domain,
            "state": state.get('state', 'unknown'),
            "command_topic": topics['command'],
            "state_topic": topics['state']
        })
    
    logger.info(f"[{g.token_name}] Returned {len(result)} full entities")
    
    return jsonify({
        "count": len(result),
        "entities": result
    })

# ============================================
# Error Handlers
# ============================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error"}), 500

# ============================================
# Main
# ============================================
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("HA Entity Resolver Starting")
    logger.info(f"  Version: 1.0.0")
    logger.info(f"  HA URL: {HA_URL}")
    logger.info(f"  Configured tokens: {len(ACCESS_TOKENS)}")
    logger.info(f"  Entity mappings: {len(ENTITY_MQTT_MAP)}")
    logger.info("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=5003,
        debug=False,
        threaded=True
    )
