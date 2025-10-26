# 🤖 Kids Chatbot Server (Zhaozhi)

Home Assistant Add-on for educational AI voice assistant for children.

## Features

- 🎤 Speech-to-Text using OpenAI Whisper
- 💬 Natural conversation using GPT-4
- 🔊 Text-to-Speech for responses
- 🛡️ Content filtering for inappropriate language
- 📚 Educational mode with polite corrections
- 🌍 Multi-language support (Vietnamese, English, Chinese, Japanese)

## Installation

1. Add this repository to your Home Assistant Add-on Store
2. Install "Kids Chatbot Server (Zhaozhi)"
3. Configure with your OpenAI API key
4. Start the add-on

## Configuration

```yaml
openai_api_key: "sk-..."
model: "gpt-4o-mini"
listening_port: 5000
language: "vi"
enable_word_filter: true
enable_educational_mode: true
