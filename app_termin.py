import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from supabase import create_client
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)
#Хранилище состояний пользователей (в памяти)
user_data ={} #{chat_id: {"step": "waiting_name", "name": "...", "article": "..."}}

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN = os.environ.get("TG_BOT_TOKEN")

def get_keyboard():
    return ReplyKeyboardMarkup(
        [["➕ Додати", "📋 Список"], ["🔍 Перевірити терміни"]],
        resize_keyboard=True
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def add_task(chat_id, name, article, deadline):
    data = {"chat_id": str(chat_id), "name": name, "article": article, "deadline": deadline}
    try:
        supabase.table("tasks").upsert(data, on_conflict="chat_id, article, deadline").execute()
        send_message(chat_id, f"✅ Додано!\n📌 {name}\n📦 {article}\n📅 {deadline}")
    except Exception as e:
        print("DB error:", e)
        send_message(chat_id, "❌ Помилка збереження")

def get_tasks(chat_id):
    try:
        res = supabase.table("tasks").select("*").eq("chat_id", chat_id).execute()
        return res.data
    except Exception as e:
        print("get_tasks error:", e)
        return []


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"status": "ok"})

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    user = msg["from"].get("first_name", "")

    # Пошаговое добавление: ожидаем название
    if chat_id in user_data and user_data[chat_id].get("step") == "waiting_name":
        user_data[chat_id]["name"] = text
        user_data[chat_id]["step"] = "waiting_article"
        send_message(chat_id, "🔢 Введи артикул:")
        return jsonify({"status": "ok"})

    # Ожидаем артикул
    if chat_id in user_data and user_data[chat_id].get("step") == "waiting_article":
        user_data[chat_id]["article"] = text
        user_data[chat_id]["step"] = "waiting_date"
        send_message(chat_id, "📅 Введи дату (ДД-ММ-РРРР):")
        return jsonify({"status": "ok"})

    # Ожидаем дату и сохраняем
    if chat_id in user_data and user_data[chat_id].get("step") == "waiting_date":
        try:
            datetime.strptime(text.strip(), "%d-%m-%Y")
            name = user_data[chat_id]["name"]
            article = user_data[chat_id]["article"]
            deadline = text.strip()
            if add_task(str(chat_id), name, article, deadline):
                send_message(chat_id, f"✅ **Додано!**\n\n📌 {name}\n📦 {article}\n📅 {deadline}")
            else:
                send_message(chat_id, "❌ Помилка при збереженні")
        except:
            send_message(chat_id, "❌ Неправильна дата! Формат: ДД-ММ-РРРР")
        finally:
            del user_data[chat_id]  # очищаем состояние
        return jsonify({"status": "ok"})

    # Обработка команд
    if text == "/start":
        send_message(chat_id, "📅 Бот для учёту термінів!\n\nОберіть дію:", get_keyboard())
        return jsonify({"status": "ok"})

    # Кнопка "Додати"
    if text == "➕ Додати":
        user_data[chat_id] = {"step": "waiting_name"}
        send_message(chat_id, "Введи назву товару:")
        return jsonify({"status": "ok"})

    # Кнопка "Список"
    if text == "📋 Список":
        tasks = get_tasks(str(chat_id))
        if not tasks:
            send_message(chat_id, "📭 Список порожній")
        else:
            msg = "📋 **Список задач:**\n\n"
            for i, t in enumerate(tasks, 1):
                msg += f"{i}. **{t['name']}**\n   📦 {t['article']}\n   📅 {t['deadline']}\n\n"
            send_message(chat_id, msg)
        return jsonify({"status": "ok"})

    # Кнопка "Перевірити терміни"
    if text == "🔍 Перевірити терміни":
        tasks = get_tasks(str(chat_id))
        if not tasks:
            send_message(chat_id, "📭 Немає задач для перевірки")
            return jsonify({"status": "ok"})

        today = datetime.now().date()
        expired = []
        urgent = []
        soon = []

        for task in tasks:
            try:
                deadline = datetime.strptime(task["deadline"], "%d-%m-%Y").date()
                days = (deadline - today).days

                if days < 0:
                    expired.append(task)
                elif 1 <= days <= 10:
                    urgent.append(task)
                elif 11 <= days <= 15:
                    soon.append(task)
            except:
                continue

        if not expired and not urgent and not soon:
            send_message(chat_id, "✅ Всьо добре! Немає задач з критичними термінами.")
            return jsonify({"status": "ok"})

        msg = "📅 **Звіт по термінам**\n\n"
        if expired:
            msg += "🔴 **ПРОСТРОЧЕНО:**\n"
            for t in expired:
                msg += f"• {t['name']} (арт. {t['article']}) ❌\n"
        if urgent:
            msg += "🟠 **ТЕРМІНОВО! (1-10 днів):**\n"
            for t in urgent:
                msg += f"• {t['name']} (арт. {t['article']}) ⏰\n"
        if soon:
            msg += "🟡 **СКОРО (11-15 днів):**\n"
            for t in soon:
                msg += f"• {t['name']} (арт. {t['article']}) 🗓️\n"

        send_message(chat_id, msg)
        return jsonify({"status": "ok"})

    # Все остальные сообщения
    send_message(chat_id, "Використовуйте кнопки 👇", get_keyboard())
    return jsonify({"status": "ok"})

@app.route('/')
def index():
    return "Бот працює!", 200

@app.route('/healthcheck')
def healthcheck():
    return "OK", 200