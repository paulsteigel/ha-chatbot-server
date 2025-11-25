#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HA Entity Endpoint Add-on
Author: Đặng Đình Ngọc (ngocdd@sfdp.net)
"""

import os
import json
import logging
from flask import Flask, jsonify, request
from functools import wraps
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration from add-on options
OPTIONS_FILE = "/data/options.json"

def load_config():
    """Load configuration from options.json"""
    try:
        with open(OPTIONS_FILE, 'r') as f:
            options = json.load(f)
            return options
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

config = load_config()
ACCESS_TOKEN = config.get('access_token', '')
HA_URL = config.get('ha_url', 'http://supervisor/core')
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')

if not ACCESS_TOKEN:
    logger.warning("Access token not configured! API will be insecure.")

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        # Support both "Bearer token" and "token" formats
        if token.startswith('Bearer '):
            token = token[7:]
        
        if ACCESS_TOKEN and token != ACCESS_TOKEN:
            return jsonify({"error": "Invalid token"}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Helper function to call Home Assistant API
def call_ha_api(endpoint, method='GET', data=None):
    """Call Home Assistant API"""
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
        logger.error(f"Error calling HA API: {e}")
        return None

# Endpoint 1: Get all areas/zones
@app.route('/api/areas', methods=['GET'])
@token_required
def get_areas():
    """Get list of all areas"""
    areas = call_ha_api('config/areas')
    if areas is None:
        return jsonify({"error": "Failed to fetch areas"}), 500
    
    return jsonify({
        "areas": [{"id": area["area_id"], "name": area["name"]} for area in areas]
    })

# Endpoint 2: Get all entities (optionally filtered by area)
@app.route('/api/entities', methods=['GET'])
@token_required
def get_entities():
    """Get all entities, optionally filtered by area"""
    area_id = request.args.get('area')
    
    states = call_ha_api('states')
    if states is None:
        return jsonify({"error": "Failed to fetch entities"}), 500
    
    # Get entity registry to map entities to areas
    entity_registry = call_ha_api('config/entity_registry')
    device_registry = call_ha_api('config/device_registry')
    
    # Create mapping of entity_id to area_id
    entity_to_area = {}
    if entity_registry:
        for entity in entity_registry:
            entity_id = entity.get('entity_id')
            area_id_from_entity = entity.get('area_id')
            device_id = entity.get('device_id')
            
            if area_id_from_entity:
                entity_to_area[entity_id] = area_id_from_entity
            elif device_id and device_registry:
                # Check device's area
                for device in device_registry:
                    if device.get('id') == device_id:
                        entity_to_area[entity_id] = device.get('area_id')
                        break
    
    # Filter entities
    result = []
    for state in states:
        entity_id = state['entity_id']
        entity_area = entity_to_area.get(entity_id)
        
        # Skip if area filter is specified and doesn't match
        if area_id and entity_area != area_id:
            continue
        
        # Only include controllable entities
        domain = entity_id.split('.')[0]
        if domain in ['light', 'switch', 'fan', 'cover', 'climate', 'lock', 'media_player']:
            result.append({
                "entity_id": entity_id,
                "name": state['attributes'].get('friendly_name', entity_id),
                "state": state['state'],
                "area_id": entity_area,
                "domain": domain,
                "attributes": state.get('attributes', {})
            })
    
    return jsonify({"entities": result})

# Endpoint 3: Get entities by area
@app.route('/api/areas/<area_id>/entities', methods=['GET'])
@token_required
def get_entities_by_area(area_id):
    """Get entities for a specific area"""
    # Reuse the get_entities logic with area filter
    request.args = {'area': area_id}
    return get_entities()

# Endpoint 4: Control entity (turn on/off)
@app.route('/api/entities/<path:entity_id>/control', methods=['POST'])
@token_required
def control_entity(entity_id):
    """Control an entity (turn on/off/toggle)"""
    data = request.get_json()
    action = data.get('action', 'toggle')  # on, off, toggle
    
    domain = entity_id.split('.')[0]
    
    # Map action to service
    service_map = {
        'on': 'turn_on',
        'off': 'turn_off',
        'toggle': 'toggle'
    }
    
    service = service_map.get(action)
    if not service:
        return jsonify({"error": "Invalid action. Use 'on', 'off', or 'toggle'"}), 400
    
    # Call Home Assistant service
    result = call_ha_api(
        'services/{}/{}'.format(domain, service),
        method='POST',
        data={'entity_id': entity_id}
    )
    
    if result is None:
        return jsonify({"error": "Failed to control entity"}), 500
    
    return jsonify({
        "success": True,
        "entity_id": entity_id,
        "action": action
    })

# Endpoint 5: Get MQTT command for entity
@app.route('/api/entities/<path:entity_id>/mqtt', methods=['GET'])
@token_required
def get_mqtt_command(entity_id):
    """Get MQTT topic and commands for an entity"""
    states = call_ha_api('states')
    if states is None:
        return jsonify({"error": "Failed to fetch entity state"}), 500
    
    # Find the entity
    entity_state = None
    for state in states:
        if state['entity_id'] == entity_id:
            entity_state = state
            break
    
    if not entity_state:
        return jsonify({"error": "Entity not found"}), 404
    
    domain = entity_id.split('.')[0]
    current_state = entity_state['state']
    
    # Generate MQTT commands
    mqtt_info = {
        "entity_id": entity_id,
        "current_state": current_state,
        "command_topic": f"homeassistant/{domain}/{entity_id.replace('.', '/')}/set",
        "state_topic": f"homeassistant/{domain}/{entity_id.replace('.', '/')}/state",
        "commands": {
            "turn_on": "ON",
            "turn_off": "OFF",
            "toggle": "TOGGLE"
        }
    }
    
    return jsonify(mqtt_info)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "addon": "ha-entity-endpoint"})

# Root endpoint with API documentation
@app.route('/', methods=['GET'])
def root():
    """API documentation"""
    return jsonify({
        "addon": "HA Entity Endpoint",
        "version": "1.0.0",
        "author": "Đặng Đình Ngọc (ngocdd@sfdp.net)",
        "endpoints": {
            "GET /api/areas": "Get all areas",
            "GET /api/entities": "Get all entities (optional ?area=area_id)",
            "GET /api/areas/{area_id}/entities": "Get entities by area",
            "POST /api/entities/{entity_id}/control": "Control entity (body: {action: on/off/toggle})",
            "GET /api/entities/{entity_id}/mqtt": "Get MQTT commands for entity"
        },
        "authentication": "Required: Authorization header with access token"
    })

if __name__ == '__main__':
    logger.info(f"Starting HA Entity Endpoint on port 5003")
    logger.info(f"Home Assistant URL: {HA_URL}")
    app.run(host='0.0.0.0', port=5003, debug=False)
