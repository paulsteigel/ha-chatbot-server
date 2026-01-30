# School Chatbot - Standalone Docker

ESP32-based AI chatbot server with Azure DeepSeek-V3.2 and Azure Speech Services.

## 🚀 Features

- ✅ **Azure DeepSeek-V3.2** via Azure OpenAI (fast & cost-effective)
- ✅ **Azure Speech SDK** (TTS with < 2s latency, no timeout!)
- ✅ **Music Playback** (YouTube audio streaming)
- ✅ **WebSocket Streaming** (real-time audio chunks)
- ✅ **MySQL Logging** (conversation history)
- ✅ **Multi-provider Fallback** (OpenAI, Piper)

## 📋 Requirements

- Docker & Docker Compose
- Azure OpenAI account (with DeepSeek deployment)
- Azure Speech Services key
- (Optional) Groq API key for STT
- (Optional) MySQL database

## 🔧 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/paulsteigel/ha-chatbot-server.git
cd ha-chatbot-server
git checkout chatbot-websocket-docker
