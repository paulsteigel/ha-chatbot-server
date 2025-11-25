import requests
from flask import Flask, jsonify, request
from functools import wraps
import os

app = Flask(__name__)

# Lấy token từ cấu hình của add-on
VALID_TOKEN = os.getenv('ACCESS_TOKEN', '')  # Lấy token từ biến môi trường

# Kiểm tra nếu không có token
if not VALID_TOKEN:
    raise ValueError("Access token must be configured in the add-on's settings.")

# Hàm xác thực token trong header của request
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or token != f"Bearer {VALID_TOKEN}":
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Lấy danh sách các entity từ Home Assistant
def get_entities_from_ha():
    response = requests.get("http://homeassistant:8123/api/states")
    entities = response.json()
    return entities

# Lọc entity theo platform và khu vực
def filter_entities(entities, platform=None, area=None):
    filtered_entities = []

    for entity in entities:
        if platform and platform not in entity['entity_id']:
            continue
        if area and area not in entity['attributes'].get('friendly_name', ''):
            continue
        filtered_entities.append(entity)
    
    return filtered_entities

@app.route('/api/entities', methods=['GET'])
@token_required
def get_all_entities():
    # Lấy danh sách tất cả entity từ Home Assistant
    entities = get_entities_from_ha()
    return jsonify([entity['entity_id'] for entity in entities])

@app.route('/api/entities/<platform>', methods=['GET'])
@token_required
def get_entities_by_platform(platform):
    entities = get_entities_from_ha()
    filtered_entities = filter_entities(entities, platform=platform)
    return jsonify([entity['entity_id'] for entity in filtered_entities])

@app.route('/api/entities/<platform>/<area>', methods=['GET'])
@token_required
def get_entities_by_platform_and_area(platform, area):
    entities = get_entities_from_ha()
    filtered_entities = filter_entities(entities, platform=platform, area=area)
    return jsonify([entity['entity_id'] for entity in filtered_entities])

@app.route('/api/zones', methods=['GET'])
@token_required
def get_zones():
    response = requests.get("http://homeassistant:8123/api/zones")
    zones = response.json()
    return jsonify(zones)

@app.route('/api/mqtt-command/<platform>/<area>/<entity_name>', methods=['GET'])
@token_required
def get_mqtt_command(platform, area, entity_name):
    entities = get_entities_from_ha()
    filtered_entities = filter_entities(entities, platform=platform, area=area)
    
    for entity in filtered_entities:
        if entity_name.lower() in entity['attributes']['friendly_name'].lower():
            mqtt_command = {
                "topic": f"homeassistant/{entity['entity_id']}/set",
                "message": "ON" if entity['state'] == "off" else "OFF"
            }
            return jsonify(mqtt_command)
    
    return jsonify({"error": "Entity not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
