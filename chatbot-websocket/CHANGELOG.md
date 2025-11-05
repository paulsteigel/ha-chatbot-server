# Changelog

## [1.0.0] - 2024-11-04

### Added
- WebSocket duplex audio streaming
- Whisper STT support
- Edge TTS with Vietnamese voices
- OpenAI/DeepSeek integration
- Context-aware conversations
- VAD (Voice Activity Detection)
- OTA firmware updates
- Web UI for device management
- Command detection (lights, volume)

### Features
- PCM 16kHz mono audio format
- Auto language detection
- Configurable silence timeout
- Persistent connections

# Changelog

## [1.0.34] - 2025-11-05

### Added
- 🚀 Groq Whisper integration for 7x faster speech-to-text
- New configuration option: `groq_api_key`

### Changed
- STT Service now uses Groq by default (with OpenAI fallback)
- Transcription latency: 1.5s → 0.2s (7.5x improvement)

### Performance
- Voice input response time dramatically improved
- Groq Whisper: ~0.2s vs OpenAI Whisper: ~1.5s

## [1.0.33] - 2025-11-05
- Previous stable version
