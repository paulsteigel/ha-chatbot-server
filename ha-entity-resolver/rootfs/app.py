#!/usr/bin/env python3
"""HA Entity Resolver - Smart entity resolution with fuzzy matching"""

from flask import Flask, request, jsonify
import requests
import json
import re
import logging
from fuzzywuzzy import fuzz
from typing import Dict, List, Optional

app = Flask(__name__)

# Configuration
CONFIG_PATH = "/data/options.json"
HA_URL = "http://supervisor/core"
HA_HEADERS = {}
entity_cache = []
area_cache = {}
device_cache = {}

def load_config():
    """Load addon configuration"""
    global HA_HEADERS
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        
        log_level = config.get("log_level", "info").upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        ha_token = config.get("ha_token", "")
        if not ha_token:
            app.logger.error("❌ HA token not configured!")
            return False
        
        HA_HEADERS["Authorization"] = f"Bearer {ha_token}"
        HA_HEADERS["Content-Type"] = "application/json"
        
        app.logger.info("✅ Configuration loaded successfully")
        return True
    except Exception as e:
        app.logger.error(f"❌ Failed to load config: {e}")
        return False

def verify_ha_token(token: str) -> bool:
    """Verify token with Home Assistant API"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{HA_URL}/api/", headers=headers, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        app.logger.debug(f"Token verification failed: {e}")
        return False

def load_ha_data():
    """Load entities, areas, and devices from Home Assistant"""
    global entity_cache, area_cache, device_cache
    
    try:
        # Load entities
        resp = requests.get(f"{HA_URL}/api/states", headers=HA_HEADERS, timeout=10)
        if resp.status_code == 200:
            entity_cache = resp.json()
            app.logger.info(f"✅ Loaded {len(entity_cache)} entities")
        
        # Load areas
        resp = requests.get(f"{HA_URL}/api/config/area_registry/list", headers=HA_HEADERS, timeout=10)
        if resp.status_code == 200:
            areas = resp.json()
            area_cache = {a['area_id']: a['name'] for a in areas}
            app.logger.info(f"✅ Loaded {len(area_cache)} areas")
        
        # Load devices
        resp = requests.get(f"{HA_URL}/api/config/device_registry/list", headers=HA_HEADERS, timeout=10)
        if resp.status_code == 200:
            devices = resp.json()
            device_cache = {
                d['id']: {
                    'name': d.get('name_by_user') or d.get('name', ''),
                    'area_id': d.get('area_id')
                } 
                for d in devices
            }
            app.logger.info(f"✅ Loaded {len(device_cache)} devices")
        
        return True
    except Exception as e:
        app.logger.error(f"❌ Failed to load HA data: {e}")
        return False

def normalize_vietnamese(text: str) -> str:
    """Normalize Vietnamese text to ASCII"""
    text = text.lower().strip()
    replacements = {
        r'[àáảãạăằắẳẵặâầấẩẫậ]': 'a',
        r'[èéẻẽẹêềếểễệ]': 'e',
        r'[ìíỉĩị]': 'i',
        r'[òóỏõọôồốổỗộơờớởỡợ]': 'o',
        r'[ùúủũụưừứửữự]': 'u',
        r'[ỳýỷỹỵ]': 'y',
        r'đ': 'd'
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r'[^\w\s]', ' ', text)

def smart_resolve(query: str) -> Optional[Dict]:
    """Resolve entity using fuzzy matching with HA hierarchy"""
    query_norm = normalize_vietnamese(query)
    candidates = []
    
    for entity in entity_cache:
        entity_id = entity['entity_id']
        attrs = entity.get('attributes', {})
        
        # Get metadata
        friendly_name = attrs.get('friendly_name', entity_id)
        device_id = attrs.get('device_id')
        area_id = None
        device_name = ""
        area_name = ""
        
        # Get device and area info
        if device_id and device_id in device_cache:
            device_info = device_cache[device_id]
            device_name = device_info['name']
            area_id = device_info['area_id']
            if area_id and area_id in area_cache:
                area_name = area_cache[area_id]
        
        # Build searchable text
        search_text = f"{friendly_name} {device_name} {area_name}"
        search_norm = normalize_vietnamese(search_text)
        
        # Fuzzy matching
        score = fuzz.token_set_ratio(query_norm, search_norm)
        
        # Bonus for exact friendly_name match
        if query_norm in normalize_vietnamese(friendly_name):
            score += 20
        
        # Bonus for matching entity_id
        if query_norm in entity_id.replace('_', ' '):
            score += 10
        
        if score >= 60:  # Threshold
            candidates.append({
                'entity_id': entity_id,
                'friendly_name': friendly_name,
                'area': area_name,
                'device': device_name,
                'state': entity['state'],
                'attributes': attrs,
                'score': score
            })
    
    # Sort by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    if candidates:
        app.logger.debug(f"Found {len(candidates)} candidates for '{query}'")
        return candidates[0]
    
    app.logger.warning(f"No match found for query: '{query}'")
    return None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    ha_connected = len(entity_cache) > 0
    return jsonify({
        'status': 'healthy' if ha_connected else 'degraded',
        'ha_connected': ha_connected,
        'entities_loaded': len(entity_cache),
        'areas_loaded': len(area_cache),
        'devices_loaded': len(device_cache),
        'version': '1.0.0'
    })

@app.route('/api/reload', methods=['POST'])
def reload_data():
    """Reload data from Home Assistant"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Bearer token'}), 401
    
    token = auth_header.replace('Bearer ', '')
    if not verify_ha_token(token):
        return jsonify({'error': 'Invalid token'}), 403
    
    success = load_ha_data()
    return jsonify({
        'success': success,
        'entities_loaded': len(entity_cache),
        'areas_loaded': len(area_cache),
        'devices_loaded': len(device_cache)
    })

@app.route('/api/resolve', methods=['POST'])
def resolve():
    """Resolve entity from natural language query"""
    # Authentication
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Bearer token'}), 401
    
    token = auth_header.replace('Bearer ', '')
    if not verify_ha_token(token):
        return jsonify({'error': 'Invalid token'}), 403
    
    # Parse request
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Reload cache if empty
    if not entity_cache:
        app.logger.info("Cache empty, reloading...")
        load_ha_data()
    
    # Resolve entity
    result = smart_resolve(query)
    
    if not result:
        return jsonify({
            'success': False,
            'message': 'No matching entity found',
            'query': query
        }), 404
    
    # Return entity info (client will build MQTT command)
    return jsonify({
        'success': True,
        'entity_id': result['entity_id'],
        'friendly_name': result['friendly_name'],
        'area': result['area'],
        'device': result['device'],
        'current_state': result['state'],
        'attributes': result['attributes'],
        'score': result['score'],
        'query': query
    })

if __name__ == '__main__':
    app.logger.info("🚀 Starting HA Entity Resolver...")
    
    if not load_config():
        app.logger.error("Failed to load configuration, exiting...")
        exit(1)
    
    if not load_ha_data():
        app.logger.warning("Failed to load initial HA data, will retry on first request")
    
    app.logger.info("✅ Server ready on port 5003")
    app.run(host='0.0.0.0', port=5003, debug=False)
