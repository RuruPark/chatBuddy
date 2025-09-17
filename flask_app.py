from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json or {}
    user_message = payload.get("userRequest", {}).get("utterance", "")
    gpt_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_message}],
    )
    reply = gpt_response.choices[0].message.content
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": reply}}]
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)