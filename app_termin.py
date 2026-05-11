import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        send_message(chat_id, f"✅ Бот бачить: {text}")
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    return "Бот працює", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))