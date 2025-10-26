# Kids ChatBot Server for Home Assistant

OpenAI-powered voice chatbot add-on cho trẻ em với giao diện test tích hợp.

## Tính năng

- ✅ Chat bằng giọng nói (Speech-to-Text + Text-to-Speech)
- ✅ Giao diện web test ngay trong add-on
- ✅ Content filtering cho trẻ em
- ✅ Hỗ trợ đa ngôn ngữ (Vietnamese, English, Japanese, Korean, Chinese)
- ✅ Nhiều giọng đọc (6 voices)
- ✅ Tùy chỉnh model OpenAI

## Cài đặt

1. Thêm repository: `https://github.com/paulsteigel/ha_chatbot_server`
2. Cài đặt add-on "Kids ChatBot Server"
3. Cấu hình OpenAI API key
4. Start add-on
5. Mở Web UI để test

## Cấu hình

- **openai_api_key**: API key từ OpenAI (bắt buộc)
- **port**: Port cho web server (mặc định: 5000)
- **language**: Ngôn ngữ (vi/en/ja/ko/zh)
- **model**: Model OpenAI (gpt-4o-mini khuyến nghị)
- **voice**: Giọng đọc (nova/alloy/echo/fable/onyx/shimmer)
- **content_filter_enabled**: Bật lọc nội dung không phù hợp

## Tác giả

Đặng Đình Ngọc <ngocdd@sfdp.net>

## License

MIT
