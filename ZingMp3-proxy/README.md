# ZingMp3-proxy

**Author:** Đặng Đình Ngọc  
**Version:** 1.0.0

Stream nhạc từ ZingMP3 cho ESP32S3 Chatbot và Home Assistant.

## Tính năng

- ✅ API tìm kiếm bài hát
- ✅ API lấy link streaming (128kbps/320kbps)
- ✅ Web interface test
- ✅ Proxy streaming (tránh CORS)
- ✅ Tối ưu cho ESP32S3

## Cài đặt

1. Add repository: `https://github.com/paulsteigel/ha-chatbot-server`
2. Install addon "ZingMp3-proxy"
3. Start addon
4. Configure Nginx Proxy Manager: `https://music.sfdp.net` → `localhost:5001`
