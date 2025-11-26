#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HA Smart Entity Gateway
Secure API with natural language support for remote devices
Author: Đặng Đình Ngọc (ngocdd@sfdp.net)
Version: 2.0.0
"""

import os
import json
import logging
from flask import Flask, jsonify, request, g
from functools import wraps
from datetime import datetime
import requests
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from rapidfuzz import fuzz, process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure cache
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

# Configure rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)

# ============================================
# Configuration Loading
# ============================================
OPTIONS_FILE = "/data/options.json"

def load_config():
    """Load configuration from options.json"""
    try:
        with open(OPTIONS_FILE, 'r') as f:
            options = json.load(f)
            logger.info("✓ Loaded config from /data/options.json")
            return options
    except Exception as e:
        logger.warning(f"Could not load /data/options.json: {e}")
        return {}

config = load_config()

# Configuration
ACCESS_TOKENS = config.get('access_tokens', [])
HA_URL = config.get('ha_url', 'http://supervisor/core')
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
RATE_LIMIT = config.get('rate_limit', 60)
ENABLE_NL = config.get('enable_natural_language', True)

# Log configuration
logger.info("=" * 60)
logger.info("HA Smart Entity Gateway Configuration:")
logger.info(f"  HA URL: {HA_URL}")
logger.info(f"  Configured Tokens: {len(ACCESS_TOKENS)}")
logger.info(f"  Rate Limit: {RATE_LIMIT}/min")
logger.info(f"  Natural Language: {'Enabled' if ENABLE_NL else 'Disabled'}")
logger.info("=" * 60)

# ============================================
# Authentication & Authorization
# ============================================
def token_required(f):
    """Authentication decorator with area-based authorization"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        # Find token config
        token_config = None
        for tc in ACCESS_TOKENS:
            if tc.get('token') == token:
                token_config = tc
                break
        
        if not token_config:
            logger.warning(f"Invalid token attempt from {get_remote_address()}")
            return jsonify({"error": "Invalid token"}), 403
        
        # Store token config in request context
        g.token_config = token_config
        g.allowed_areas = token_config.get('areas', [])
        g.token_name = token_config.get('name', 'Unknown')
        
        return f(*args, **kwargs)
    return decorated_function

def check_area_permission(area_id):
    """Check if current token has access to area"""
    allowed_areas = g.get('allowed_areas', [])
    # Empty list means access to all areas
    if not allowed_areas:
        return True
    return area_id in allowed_areas

# ============================================
# Home Assistant API Helper
# ============================================
@cache.memoize(timeout=30)
def call_ha_api(endpoint, method='GET', data=None):
    """Call Home Assistant API with caching"""
    url = f"{HA_URL}/api/{endpoint}"
    headers = {
        'Authorization': f'Bearer {SUPERVISOR_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=10)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error calling HA API ({endpoint}): {e}")
        return None

# ============================================
# Natural Language Processing
# ============================================
def parse_natural_language_query(query):
    """
    Parse natural language query like:
    "Bật đèn tầng 2 nhà Ngọc ở Hà Nội"
    Returns: (action, entity_keywords, area_keywords)
    """
    query = query.lower()
    
    # Detect action
    action = None
    if any(word in query for word in ['bật', 'turn on', 'on', 'mở']):
        action = 'turn_on'
    elif any(word in query for word in ['tắt', 'turn off', 'off', 'đóng']):
        action = 'turn_off'
    elif any(word in query for word in ['toggle', 'chuyển', 'đảo']):
        action = 'toggle'
    elif any(word in query for word in ['trạng thái', 'status', 'state', 'thế nào']):
        action = 'get_state'
    
    # Extract keywords (simple approach - can be improved with NLP)
    keywords = [w for w in query.split() if len(w) > 2]
    
    return action, keywords

def fuzzy_match_entity(keywords, entities):
    """Fuzzy match entity names against keywords"""
    results = []
    
    for entity in entities:
        # Combine searchable text
        search_text = f"{entity['name']} {entity['entity_id']} {entity.get('area_name', '')}"
        
        # Calculate match score
        max_score = 0
        for keyword in keywords:
            score = fuzz.partial_ratio(keyword, search_text.lower())
            max_score = max(max_score, score)
        
        if max_score > 60:  # Threshold
            results.append((entity, max_score))
    
    # Sort by score
    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results[:5]]  # Top 5 matches

# ============================================
# API Endpoints
# ============================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/', methods=['GET'])
def root():
    """API documentation"""
    return jsonify({
        "addon": "HA Smart Entity Gateway",
        "version": "2.0.0",
        "author": "Đặng Đình Ngọc (ngocdd@sfdp.net)",
        "endpoints": {
            "GET /api/areas": "Get all accessible areas",
            "GET /api/entities": "Get entities (optional: ?area=id&domain=switch,light)",
            "POST /api/query": "Natural language query (body: {query: 'string'})",
            "POST /api/control": "Control entity (body: {entity_id, action})",
            "GET /api/entity/<entity_id>": "Get single entity info"
        },
        "authentication": "Required: Authorization: Bearer <token>"
    })

@app.route('/api/areas', methods=['GET'])
@token_required
@limiter.limit(f"{RATE_LIMIT} per minute")
def get_areas():
    """Get all areas (filtered by token permissions)"""
    areas = call_ha_api('config/area_registry')
    if not areas:
        return jsonify({"error": "Failed to fetch areas"}), 500
    
    allowed = g.get('allowed_areas', [])
    
    if allowed:
        areas = [a for a in areas if a['area_id'] in allowed]
    
    return jsonify({
        "areas": [
            {
                "id": area["area_id"],
                "name": area["name"],
                "aliases": area.get("aliases", [])
            }
            for area in areas
        ]
    })

@app.route('/api/entities', methods=['GET'])
@token_required
@limiter.limit(f"{RATE_LIMIT} per minute")
@cache.cached(timeout=10, query_string=True)
def get_entities():
    """Get entities with optional filters"""
    area_filter = request.args.get('area')
    domain_filter = request.args.get('domain', '').split(',')
    domain_filter = [d.strip() for d in domain_filter if d.strip()]
    
    # Get all states
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entities"}), 500
    
    # Get registries for area mapping
    entity_registry = call_ha_api('config/entity_registry') or []
    device_registry = call_ha_api('config/device_registry') or []
    area_registry = call_ha_api('config/area_registry') or []
    
    # Create mappings
    entity_to_area = {}
    device_to_area = {d['id']: d.get('area_id') for d in device_registry}
    area_names = {a['area_id']: a['name'] for a in area_registry}
    
    for entity in entity_registry:
        entity_id = entity.get('entity_id')
        area_id = entity.get('area_id')
        
        if not area_id and entity.get('device_id'):
            area_id = device_to_area.get(entity.get('device_id'))
        
        if area_id:
            entity_to_area[entity_id] = area_id
    
    # Filter entities
    result = []
    allowed_areas = g.get('allowed_areas', [])
    
    for state in states:
        entity_id = state['entity_id']
        domain = entity_id.split('.')[0]
        
        # Domain filter
        if domain_filter and domain not in domain_filter:
            continue
        
        # Only controllable entities
        if domain not in ['light', 'switch', 'fan', 'cover', 'climate', 'lock', 'media_player']:
            continue
        
        # Area permission check
        entity_area = entity_to_area.get(entity_id)
        if allowed_areas and entity_area not in allowed_areas:
            continue
        
        if area_filter and entity_area != area_filter:
            continue
        
        result.append({
            "entity_id": entity_id,
            "name": state['attributes'].get('friendly_name', entity_id),
            "state": state['state'],
            "area_id": entity_area,
            "area_name": area_names.get(entity_area, "No Area"),
            "domain": domain,
            "attributes": {
                k: v for k, v in state.get('attributes', {}).items()
                if k in ['brightness', 'temperature', 'current_temperature', 'hvac_mode']
            }
        })
    
    return jsonify({
        "count": len(result),
        "entities": result
    })

@app.route('/api/entity/<path:entity_id>', methods=['GET'])
@token_required
@limiter.limit(f"{RATE_LIMIT} per minute")
def get_entity(entity_id):
    """Get single entity with full details"""
    states = call_ha_api('states')
    if not states:
        return jsonify({"error": "Failed to fetch entity"}), 500
    
    entity_state = next((s for s in states if s['entity_id'] == entity_id), None)
    if not entity_state:
        return jsonify({"error": "Entity not found"}), 404
    
    # Check area permission
    entity_registry = call_ha_api('config/entity_registry') or []
    device_registry = call_ha_api('config/device_registry') or []
    
    entity_info = next((e for e in entity_registry if e['entity_id'] == entity_id), {})
    area_id = entity_info.get('area_id')
    
    if not area_id and entity_info.get('device_id'):
        device = next((d for d in device_registry if d['id'] == entity_info['device_id']), {})
        area_id = device.get('area_id')
    
    if not check_area_permission(area_id):
        return jsonify({"error": "Access denied to this entity"}), 403
    
    return jsonify({
        "entity_id": entity_id,
        "name": entity_state['attributes'].get('friendly_name', entity_id),
        "state": entity_state['state'],
        "area_id": area_id,
        "domain": entity_id.split('.')[0],
        "attributes": entity_state.get('attributes', {}),
        "last_changed": entity_state.get('last_changed'),
        "last_updated": entity_state.get('last_updated')
    })

@app.route('/api/control', methods=['POST'])
@token_required
@limiter.limit(f"{RATE_LIMIT} per minute")
def control_entity():
    """Control an entity"""
    data = request.get_json()
    
    entity_id = data.get('entity_id')
    action = data.get('action')  # turn_on, turn_off, toggle
    
    if not entity_id or not action:
        return jsonify({"error": "Missing entity_id or action"}), 400
    
    # Check permission (reuse get_entity logic)
    entity_response = get_entity(entity_id)
    if entity_response[1] != 200:  # Not authorized
        return entity_response
    
    domain = entity_id.split('.')[0]
    service = action
    
    # Call service
    result = call_ha_api(
        f'services/{domain}/{service}',
        method='POST',
        data={'entity_id': entity_id}
    )
    
    if result is None:
        return jsonify({"error": "Failed to control entity"}), 500
    
    logger.info(f"[{g.token_name}] Controlled {entity_id}: {action}")
    
    return jsonify({
        "success": True,
        "entity_id": entity_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/api/query', methods=['POST'])
@token_required
@limiter.limit(f"{RATE_LIMIT} per minute")
def natural_language_query():
    """
    Process natural language query
    Example: {"query": "Bật đèn tầng 2 nhà Ngọc"}
    """
    if not ENABLE_NL:
        return jsonify({"error": "Natural language processing disabled"}), 400
    
    data = request.get_json()
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "Missing query"}), 400
    
    # Parse query
    action, keywords = parse_natural_language_query(query)
    
    if not action:
        return jsonify({
            "error": "Could not determine action",
            "hint": "Use words like: bật, tắt, trạng thái, toggle"
        }), 400
    
    # Get all accessible entities
    entities_response = get_entities()
    if entities_response[1] != 200:
        return entities_response
    
    entities = entities_response[0].get_json()['entities']
    
    # Fuzzy match
    matches = fuzzy_match_entity(keywords, entities)
    
    if not matches:
        return jsonify({
            "error": "No matching entities found",
            "keywords": keywords,
            "entities_searched": len(entities)
        }), 404
    
    # If action is get_state, return all matches
    if action == 'get_state':
        return jsonify({
            "query": query,
            "action": action,
            "matches": [
                {
                    "entity_id": m['entity_id'],
                    "name": m['name'],
                    "state": m['state'],
                    "area": m.get('area_name')
                }
                for m in matches
            ]
        })
    
    # For control actions, use best match
    best_match = matches[0]
    
    # Execute control
    control_result = control_entity.__wrapped__().__wrapped__()  # Bypass decorators
    request.json = {
        'entity_id': best_match['entity_id'],
        'action': action
    }
    
    return jsonify({
        "query": query,
        "matched_entity": {
            "entity_id": best_match['entity_id'],
            "name": best_match['name'],
            "area": best_match.get('area_name')
        },
        "action": action,
        "executed": True
    })

if __name__ == '__main__':
    logger.info(f"Starting HA Smart Entity Gateway on port 5003")
    app.run(host='0.0.0.0', port=5003, debug=False)
