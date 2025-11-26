#!/usr/bin/env python3
"""
HA Entity Resolver Addon
Smart entity resolution with fuzzy matching and control
"""

import os
import json
import logging
import time
from flask import Flask, request, jsonify
import requests
from rapidfuzz import fuzz, process

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get supervisor token (automatic)
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN')
HA_URL = "http://supervisor/core/api"

# Headers for HA API calls
HA_HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json"
}

# Cache configuration
CACHE_DURATION = int(os.environ.get('CACHE_DURATION', '60'))
entities_cache = []
cache_timestamp = 0


def refresh_entities_cache():
    """Fetch and cache all entities from HA"""
    global entities_cache, cache_timestamp
    
    try:
        response = requests.get(
            f"{HA_URL}/states",
            headers=HA_HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            entities_cache = response.json()
            cache_timestamp = time.time()
            logger.info(f"Cached {len(entities_cache)} entities")
            return True
        else:
            logger.error(f"Failed to fetch entities: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error fetching entities: {e}")
        return False


def verify_token(token):
    """Verify token with Home Assistant API"""
    try:
        response = requests.get(
            f"{HA_URL}/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return False


def fuzzy_match_entity(query, area=None, domain=None, min_score=70):
    """
    Find best matching entity using fuzzy matching
    
    Args:
        query: Search query (e.g., "den bep", "light kitchen")
        area: Optional area filter
        domain: Optional domain filter (light, switch, fan...)
        min_score: Minimum fuzzy match score (0-100)
    
    Returns:
        dict: Best matching entity info or None
    """
    global cache_timestamp
    
    # Refresh cache if expired
    if time.time() - cache_timestamp > CACHE_DURATION:
        refresh_entities_cache()
    
    if not entities_cache:
        return None
    
    # Build searchable candidates
    search_candidates = []
    for entity in entities_cache:
        entity_id = entity.get('entity_id', '')
        entity_domain = entity_id.split('.')[0] if '.' in entity_id else ''
        friendly_name = entity.get('attributes', {}).get('friendly_name', '')
        entity_area = entity.get('attributes', {}).get('area', '')
        
        # Apply filters
        if area and entity_area.lower() != area.lower():
            continue
        
        if domain and entity_domain != domain:
            continue
        
        # Only include controllable entities
        if entity_domain not in ['light', 'switch', 'fan', 'climate', 'cover', 'lock', 'media_player']:
            continue
        
        # Combine search fields
        search_string = f"{friendly_name} {entity_id} {entity_area}".lower()
        search_candidates.append({
            'search_string': search_string,
            'entity': entity
        })
    
    if not search_candidates:
        return None
    
    # Fuzzy match
    query_lower = query.lower()
    matches = process.extract(
        query_lower,
        [c['search_string'] for c in search_candidates],
        scorer=fuzz.WRatio,
        limit=3  # Get top 3 for alternatives
    )
    
    if not matches or matches[0][1] < min_score:
        return None
    
    # Get best match
    best_match_idx = [c['search_string'] for c in search_candidates].index(matches[0][0])
    best_entity = search_candidates[best_match_idx]['entity']
    
    # Get alternatives (if score < 90)
    alternatives = []
    if matches[0][1] < 90 and len(matches) > 1:
        for match in matches[1:3]:
            if match[1] >= min_score:
                alt_idx = [c['search_string'] for c in search_candidates].index(match[0])
                alt_entity = search_candidates[alt_idx]['entity']
                alternatives.append({
                    'entity_id': alt_entity.get('entity_id'),
                    'friendly_name': alt_entity.get('attributes', {}).get('friendly_name'),
                    'match_score': match[1]
                })
    
    # Extract entity info
    entity_id = best_entity.get('entity_id')
    domain = entity_id.split('.')[0] if '.' in entity_id else ''
    
    # Get supported actions based on domain
    supported_actions = get_supported_actions(domain, best_entity.get('attributes', {}))
    
    result = {
        'entity_id': entity_id,
        'friendly_name': best_entity.get('attributes', {}).get('friendly_name', entity_id),
        'state': best_entity.get('state'),
        'domain': domain,
        'area': best_entity.get('attributes', {}).get('area'),
        'device_class': best_entity.get('attributes', {}).get('device_class'),
        'match_score': matches[0][1],
        'supported_actions': supported_actions,
        'attributes': best_entity.get('attributes', {})
    }
    
    if alternatives:
        result['alternatives'] = alternatives
    
    return result


def get_supported_actions(domain, attributes):
    """Get supported actions for a domain"""
    actions = ['turn_on', 'turn_off', 'toggle']
    
    if domain == 'light':
        if attributes.get('supported_color_modes'):
            actions.append('brightness')
            if 'rgb' in attributes.get('supported_color_modes', []):
                actions.append('color')
    elif domain == 'climate':
        actions = ['turn_on', 'turn_off', 'set_temperature', 'set_hvac_mode']
    elif domain == 'cover':
        actions = ['open_cover', 'close_cover', 'stop_cover', 'set_cover_position']
    elif domain == 'lock':
        actions = ['lock', 'unlock']
    elif domain == 'media_player':
        actions = ['turn_on', 'turn_off', 'volume_up', 'volume_down', 'media_play', 'media_pause']
    
    return actions


def execute_action(entity_id, action, parameters=None):
    """
    Execute action on entity using HA Service API
    
    Args:
        entity_id: Target entity ID
        action: Action to perform (turn_on, turn_off, etc.)
        parameters: Optional parameters (brightness, temperature, etc.)
    
    Returns:
        dict: Result with success status and new state
    """
    domain = entity_id.split('.')[0]
    
    # Map action to service
    service_map = {
        'turn_on': 'turn_on',
        'turn_off': 'turn_off',
        'toggle': 'toggle',
        'brightness': 'turn_on',
        'color': 'turn_on',
        'set_temperature': 'set_temperature',
        'set_hvac_mode': 'set_hvac_mode',
        'open_cover': 'open_cover',
        'close_cover': 'close_cover',
        'stop_cover': 'stop_cover',
        'set_cover_position': 'set_cover_position',
        'lock': 'lock',
        'unlock': 'unlock',
        'volume_up': 'volume_up',
        'volume_down': 'volume_down',
        'media_play': 'media_play',
        'media_pause': 'media_pause'
    }
    
    service = service_map.get(action)
    if not service:
        return {'success': False, 'error': f'Unknown action: {action}'}
    
    # Build service call data
    service_data = {'entity_id': entity_id}
    
    # Add parameters if provided
    if parameters:
        if action == 'brightness' and 'brightness' in parameters:
            service_data['brightness'] = parameters['brightness']
        elif action == 'color' and 'rgb_color' in parameters:
            service_data['rgb_color'] = parameters['rgb_color']
        elif action == 'set_temperature' and 'temperature' in parameters:
            service_data['temperature'] = parameters['temperature']
        elif action == 'set_hvac_mode' and 'hvac_mode' in parameters:
            service_data['hvac_mode'] = parameters['hvac_mode']
        elif action == 'set_cover_position' and 'position' in parameters:
            service_data['position'] = parameters['position']
    
    try:
        # Get previous state
        prev_response = requests.get(
            f"{HA_URL}/states/{entity_id}",
            headers=HA_HEADERS,
            timeout=5
        )
        previous_state = prev_response.json().get('state') if prev_response.status_code == 200 else 'unknown'
        
        # Call service
        response = requests.post(
            f"{HA_URL}/services/{domain}/{service}",
            headers=HA_HEADERS,
            json=service_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            # Get new state (wait a bit for state to update)
            time.sleep(0.3)
            new_response = requests.get(
                f"{HA_URL}/states/{entity_id}",
                headers=HA_HEADERS,
                timeout=5
            )
            new_state = new_response.json().get('state') if new_response.status_code == 200 else 'unknown'
            
            logger.info(f"Executed {action} on {entity_id}: {previous_state} → {new_state}")
            
            return {
                'success': True,
                'previous_state': previous_state,
                'new_state': new_state
            }
        else:
            logger.error(f"Service call failed: {response.status_code} - {response.text}")
            return {'success': False, 'error': f'Service call failed: {response.status_code}'}
            
    except Exception as e:
        logger.error(f"Error executing action: {e}")
        return {'success': False, 'error': str(e)}


@app.route('/api/control', methods=['POST'])
def control_entity():
    """
    Resolve entity and execute action
    
    Request:
        {
            "query": "đèn phòng ngủ",
            "action": "turn_on",
            "area": "tầng 2",  // optional
            "domain": "light",  // optional
            "parameters": {  // optional
                "brightness": 128
            }
        }
    
    Response:
        {
            "success": true,
            "entity_id": "light.den_phong_ngu",
            "friendly_name": "Đèn phòng ngủ",
            "action": "turn_on",
            "match_score": 95,
            "previous_state": "off",
            "new_state": "on"
        }
    """
    
    # Verify token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    if not verify_token(token):
        return jsonify({'error': 'Invalid token'}), 403
    
    # Get request data
    data = request.get_json()
    if not data or 'query' not in data or 'action' not in data:
        return jsonify({'error': 'Missing query or action parameter'}), 400
    
    query = data.get('query')
    action = data.get('action')
    area = data.get('area')
    domain = data.get('domain')
    parameters = data.get('parameters')
    min_score = data.get('min_score', 70)
    
    # Find matching entity
    entity = fuzzy_match_entity(query, area, domain, min_score)
    
    if not entity:
        return jsonify({'error': 'No matching entity found'}), 404
    
    # Check if action is supported
    if action not in entity['supported_actions']:
        return jsonify({
            'error': f"Action '{action}' not supported for this entity",
            'supported_actions': entity['supported_actions']
        }), 400
    
    # Execute action
    result = execute_action(entity['entity_id'], action, parameters)
    
    # Build response
    response = {
        'success': result.get('success', False),
        'entity_id': entity['entity_id'],
        'friendly_name': entity['friendly_name'],
        'action': action,
        'match_score': entity['match_score']
    }
    
    if result.get('success'):
        response['previous_state'] = result.get('previous_state')
        response['new_state'] = result.get('new_state')
    else:
        response['error'] = result.get('error', 'Unknown error')
    
    if 'alternatives' in entity:
        response['alternatives'] = entity['alternatives']
    
    logger.info(f"Control '{query}' → {entity['entity_id']}.{action} (score: {entity['match_score']})")
    
    return jsonify(response), 200 if result.get('success') else 500


@app.route('/api/resolve', methods=['POST'])
def resolve_entity():
    """
    Resolve entity from natural language query (without executing action)
    
    Request:
        {
            "query": "đèn phòng ngủ",
            "area": "tầng 2",  // optional
            "domain": "light",  // optional
            "min_score": 70  // optional
        }
    
    Response:
        {
            "entity_id": "light.den_phong_ngu",
            "friendly_name": "Đèn phòng ngủ",
            "state": "off",
            "domain": "light",
            "area": "Tầng 2",
            "match_score": 95,
            "supported_actions": ["turn_on", "turn_off", "toggle"]
        }
    """
    
    # Verify token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    if not verify_token(token):
        return jsonify({'error': 'Invalid token'}), 403
    
    # Get request data
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    query = data.get('query')
    area = data.get('area')
    domain = data.get('domain')
    min_score = data.get('min_score', 70)
    
    # Find matching entity
    result = fuzzy_match_entity(query, area, domain, min_score)
    
    if not result:
        return jsonify({'error': 'No matching entity found'}), 404
    
    logger.info(f"Resolved '{query}' → {result['entity_id']} (score: {result['match_score']})")
    
    return jsonify(result), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'entities_cached': len(entities_cache),
        'cache_age_seconds': int(time.time() - cache_timestamp) if cache_timestamp else None
    }), 200


if __name__ == '__main__':
    logger.info("Starting HA Entity Resolver...")
    
    if not SUPERVISOR_TOKEN:
        logger.error("SUPERVISOR_TOKEN not found!")
    else:
        logger.info("SUPERVISOR_TOKEN detected")
        refresh_entities_cache()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5003, debug=False)
