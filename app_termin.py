import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from supabase import create_client

app = Flask(__name__)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def get_keyboard():
    return {
        "keyboard": [
            [{"text": "➕ Додати"}, {"text": "📋 Список"}],
            [{"text": "🔍 Перевірити терміни"}]
        ],
        "resize_keyboard": True
    }

def get_tasks(chat_id):
    try:
        res = supabase.table("tasks").select("*").eq("chat_id", str(chat_id)).execute()
        return res.data
    except Exception as e:
        print("DB get error:", e)
        return []

def add_task(chat_id, name, article, deadline):
    print(f"💾 Сохраняю: {chat_id}, {name}, {article}, {deadline}", flush=True)
    data = {
        "chat_id": str(chat_id),
        "name": name,
        "article": article,
        "deadline": deadline
    }
    try:
        supabase.table("tasks").upsert(data, on_conflict="chat_id, article, deadline").execute()
        return True
    except Exception as e:
        print("DB add error:", e, flush=True)
        return False

user_steps = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"status": "ok"})

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text == "/start":
        send_message(chat_id, "📅 Бот для учёту термінів!\n\nОберіть дію:", get_keyboard())
        return jsonify({"status": "ok"})

    if text == "📋 Список":
        tasks = get_tasks(chat_id)
        if not tasks:
            send_message(chat_id, "📭 Список порожній")
            return jsonify({"status": "ok"})
        msg = "📋 **Список задач:**\n\n"
        for i, t in enumerate(tasks, 1):
            msg += f"{i}. **{t['name']}**\n   📦 {t['article']}\n   📅 {t['deadline']}\n\n"
        send_message(chat_id, msg)
        return jsonify({"status": "ok"})

    if text == "🔍 Перевірити терміни":
        send_message(chat_id, "⏳ Функція в розробці")
        return jsonify({"status": "ok"})

    if text == "➕ Додати":
        user_steps[chat_id] = {"step": "waiting_name"}
        send_message(chat_id, "📝 Введи назву товару:")
        return jsonify({"status": "ok"})

    if chat_id in user_steps:
        if user_steps[chat_id]["step"] == "waiting_name":
            user_steps[chat_id]["name"] = text
            user_steps[chat_id]["step"] = "waiting_article"
            send_message(chat_id, "🔢 Введи артикул:")
            return jsonify({"status": "ok"})

        if user_steps[chat_id]["step"] == "waiting_article":
            user_steps[chat_id]["article"] = text
            user_steps[chat_id]["step"] = "waiting_date"
            send_message(chat_id, "📅 Введи дату (ДД-ММ-РРРР):")
            return jsonify({"status": "ok"})

        if user_steps[chat_id]["step"] == "waiting_date":
            try:
                datetime.strptime(text, "%d-%m-%Y")
                add_task(chat_id, user_steps[chat_id]["name"], user_steps[chat_id]["article"], text)
                send_message(chat_id, f"✅ **Додано!**\n📌 {user_steps[chat_id]['name']}\n📦 {user_steps[chat_id]['article']}\n📅 {text}")
            except:
                send_message(chat_id, "❌ Неправильна дата! Формат: ДД-ММ-РРРР")
            finally:
                del user_steps[chat_id]
            return jsonify({"status": "ok"})

    send_message(chat_id, "Використовуйте кнопки 👇", get_keyboard())
    return jsonify({"status": "ok"})

@app.route('/')
def index():
    return "✅ Бот працює", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"status": "ok"})
    # ... обработка
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))