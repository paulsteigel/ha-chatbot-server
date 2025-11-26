Response:


{
  "success": true,
  "entity_id": "light.den_phong_ngu_tang_2",
  "friendly_name": "Đèn phòng ngủ tầng 2",
  "action": "turn_on",
  "match_score": 95,
  "previous_state": "off",
  "new_state": "on"
}
2. Resolve Entity (No Execution)

POST http://homeassistant.local:5003/api/resolve
Authorization: Bearer YOUR_LONG_LIVED_TOKEN
Content-Type: application/json

{
  "query": "đèn bếp",
  "area": "tầng 1",
  "min_score": 70
}
Response:


{
  "entity_id": "light.den_bep",
  "friendly_name": "Đèn bếp",
  "state": "off",
  "domain": "light",
  "area": "Tầng 1",
  "match_score": 95,
  "supported_actions": ["turn_on", "turn_off", "toggle", "brightness"]
}
Supported Actions
light: turn_on, turn_off, toggle, brightness, color
switch: turn_on, turn_off, toggle
fan: turn_on, turn_off, toggle
climate: turn_on, turn_off, set_temperature, set_hvac_mode
cover: open_cover, close_cover, stop_cover, set_cover_position
lock: lock, unlock
media_player: turn_on, turn_off, volume_up, volume_down, media_play, media_pause
ESP32 Example

#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* HA_TOKEN = "your_long_lived_token_here";
const char* ADDON_URL = "http://homeassistant.local:5003/api/control";

void controlDevice(String query, String action) {
  HTTPClient http;
  http.begin(ADDON_URL);
  http.addHeader("Authorization", String("Bearer ") + HA_TOKEN);
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<256> doc;
  doc["query"] = query;
  doc["action"] = action;
  
  String payload;
  serializeJson(doc, payload);
  
  int httpCode = http.POST(payload);
  
  if (httpCode == 200) {
    String response = http.getString();
    StaticJsonDocument<1024> responseDoc;
    deserializeJson(responseDoc, response);
    
    bool success = responseDoc["success"];
    String entity_id = responseDoc["entity_id"];
    String new_state = responseDoc["new_state"];
    
    Serial.printf("Success: %d, Entity: %s, State: %s\n", 
                  success, entity_id.c_str(), new_state.c_str());
  }
  
  http.end();
}

void setup() {
  Serial.begin(115200);
  // Setup WiFi...
  
  // Example: Turn on bedroom light
  controlDevice("đèn phòng ngủ", "turn_on");
}
Troubleshooting
Addon not starting
Check logs in Home Assistant
Verify SUPERVISOR_TOKEN is available
"Invalid token" error from ESP32
Verify your long-lived token is correct
Check token hasn't expired
"No matching entity found"
Check entity exists in Home Assistant
Try lowering min_score (default: 70)
Add area or domain filters
Action not supported
Check supported_actions in response
Different entity types support different actions
Support
Report issues at: https://github.com/paulsteigel/ha-chatbot-server/issues



---

### **8. `CHANGELOG.md`**
```markdown
# Changelog

## [1.0.0] - 2024-01-XX

### Added
- Initial release
- Fuzzy entity matching with confidence scores
- Direct control via `/api/control` endpoint
- Read-only resolve via `/api/resolve` endpoint
- Token authentication via HA long-lived tokens
- Entity caching with configurable duration
- Support for all major entity types (light, switch, fan, climate, cover, lock, media_player)
- Area and domain filtering
- Smart alternatives when match confidence is low
- Health check endpoint
9. README.md (root)

# HA Chatbot Server

Collection of Home Assistant addons for voice assistant and ESP32 integration.

## Addons

### HA Entity Resolver
Smart entity resolver with fuzzy matching and direct control for ESP32 voice assistants.

**Features:**
- Natural language entity resolution
- Direct control via Home Assistant API
- Fuzzy matching with confidence scores
- Support for all major entity types

[📖 Full Documentation](ha-entity-resolver/DOCS.md)

## Installation

1. In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Click **⋮** (top right) → **Repositories**
3. Add: `https://github.com/paulsteigel/ha-chatbot-server`
4. Install **HA Entity Resolver**

## Quick Start

1. Create a Long-Lived Token in HA Profile → Security
2. Hard-code token in your ESP32 firmware
3. Call addon API:

```cpp
POST http://homeassistant.local:5003/api/control
Authorization: Bearer YOUR_TOKEN
{
  "query": "turn on bedroom light",
  "action": "turn_on"
}
License
MIT



---

## ✅ **Xong! Bạn có thể:**

1. Copy các file này vào GitHub repo
2. Tạo icon/logo (tôi có thể gợi ý nếu cần)
3. Test addon trong HA

**Có thắc mắc gì về code không?** 🚀