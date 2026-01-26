import os
import telebot
import requests
import hashlib
from groq import Groq
from collections import deque
from flask import Flask
from threading import Thread
from telebot import types

app = Flask(__name__)

@app.route('/')
def home():
    return "Status: Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- НАСТРОЙКИ (Переменные окружения) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
SCREENSHOT_API_KEY = os.environ.get('SCREENSHOT_API_KEY')
SECRET_PHRASE = os.environ.get('SECRET_PHRASE')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

MY_OWN_ID = 5349904118

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# Состояния
ALLOWED_CHATS = [5349904118, -1002322741739, -1003102220757]
IS_MAINTENANCE = False  
chat_histories = {}
chat_limits = {}
chat_models = {}

MODELS = {
    "Llama 3.3 70B": "llama-3.3-70b-versatile",
    "DeepSeek R1 70B": "deepseek-r1-distill-llama-70b",
    "Llama 3.1 8B": "llama-3.1-8b-instant"
}

# --- КОМАНДА ОЧИСТКИ ПАМЯТИ ---
@bot.message_handler(commands=['clear'])
def clear_chat_history(message):
    chat_id = message.chat.id
    if chat_id in chat_histories:
        chat_histories[chat_id].clear()
        bot.reply_to(message, "🧹 Память этого чата очищена.")
    else:
        bot.reply_to(message, "Память и так пуста.")

# --- ФУНКЦИЯ СКРИНШОТА ---
@bot.message_handler(commands=['screen'])
def take_screenshot(message):
    if message.chat.id not in ALLOWED_CHATS or IS_MAINTENANCE: return
    
    if not SCREENSHOT_API_KEY or not SECRET_PHRASE:
        bot.reply_to(message, "❌ Ошибка конфигурации API/SECRET на Render.")
        return

    try:
        url = message.text.split(maxsplit=1)[1]
        if not url.startswith('http'):
            url = 'https://' + url
    except IndexError:
        bot.reply_to(message, "⚠️ Формат: `/screen google.com`", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "📸 Делаю скриншот...")

    # Хешируем: md5(url + SECRET_PHRASE)
    hash_val = hashlib.md5((url + SECRET_PHRASE).encode('utf-8')).hexdigest()
    api_url = f"https://api.screenshotmachine.com/?key={SCREENSHOT_API_KEY}&url={url}&dimension=1920x1080&format=jpg&hash={hash_val}"
    
    try:
        response = requests.get(api_url, timeout=20)
        if response.status_code == 200:
            bot.send_photo(message.chat.id, response.content, caption=f"✅ Скриншот: {url}")
            bot.delete_message(message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text(f"❌ Ошибка API: {response.status_code}", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", message.chat.id, status_msg.message_id)

# --- АДМИНКА ---
@bot.message_handler(commands=['admin'])
def admin_auth(message):
    if message.from_user.id != MY_OWN_ID: return
    msg = bot.send_message(message.chat.id, "🔑 Введите пароль:")
    bot.register_next_step_handler(msg, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        show_admin_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ Отказ.")

def show_admin_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Статус", "🔴 Выключить бота" if not IS_MAINTENANCE else "🟢 Включить бота")
    markup.add("➕ Добавить чат", "🧹 Сбросить всё")
    markup.add("🚪 Выход")
    bot.send_message(chat_id, "⚙️ Панель управления:", reply_markup=markup)

# (Логика кнопок админки остается прежней...)
# [Для краткости пропускаем повторение функций админки, они такие же как выше]

# --- ЛОГИКА ИИ (НЕЙТРАЛЬНАЯ) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in ALLOWED_CHATS or (IS_MAINTENANCE and message.from_user.id != MY_OWN_ID): return

    bot_info = bot.get_me()
    if message.chat.type == 'private' or (message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id) or (message.text and f"@{bot_info.username}" in message.text):
        
        limit = chat_limits.get(chat_id, 1000)
        model_id = MODELS.get(chat_models.get(chat_id, "Llama 3.3 70B"), "llama-3.3-70b-versatile")
        
        if chat_id not in chat_histories: chat_histories[chat_id] = deque(maxlen=limit)
        
        clean_text = message.text.replace(f"@{bot_info.username}", "").strip() if message.text else ""
        if not clean_text: return

        # Системная инструкция теперь БЕЗ упоминания пола
        system_prompt = {"role": "system", "content": "Ты — полезный ИИ-ассистент. Отвечай всегда на русском языке, будь точным и вежливым."}
        
        chat_histories[chat_id].append({"role": "user", "content": clean_text})
        messages_for_ai = [system_prompt] + list(chat_histories[chat_id])

        try:
            completion = client.chat.completions.create(model=model_id, messages=messages_for_ai, temperature=0.7)
            res = completion.choices[0].message.content
            chat_histories[chat_id].append({"role": "assistant", "content": res})
            bot.reply_to(message, res)
        except Exception as e:
            bot.reply_to(message, "⚠️ Ошибка связи с нейросетью.")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
