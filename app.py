from flask import Flask, request, jsonify, send_file
import openai, tempfile, os
from pydub import AudioSegment

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

@app.route("/ask", methods=["POST"])
def ask():
    if 'audio' not in request.files:
        return jsonify({"error": "no audio uploaded"}), 400

    audio_file = request.files['audio']
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_file.save(tmp.name)
        tmp.flush()

        # Whisper - Speech to Text
        transcript = openai.Audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=open(tmp.name, "rb")
        ).text

        print("User asked:", transcript)

        # GPT - Chat completion
        response = openai.Chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là trợ lý thân thiện cho học sinh tiểu học."},
                {"role": "user", "content": transcript}
            ]
        )

        answer = response.choices[0].message.content
        print("Bot:", answer)

        # TTS - Text to Speech
        speech_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        with openai.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=answer,
        ) as resp:
            resp.stream_to_file(speech_path)

        return send_file(speech_path, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

