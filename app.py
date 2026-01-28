import os
import telebot
import time
from duckduckgo_search import DDGS
from collections import deque
from flask import Flask
from threading import Thread

# Попытка установить библиотеку, если её нет (для Render)
try:
    from duckduckgo_search import DDGS
except ImportError:
    os.system('pip install -U duckduckgo_search')
    from duckduckgo_search import DDGS

app = Flask(__name__)

@app.route('/')
def home(): 
    return "Warden System: Total Control via Duck. ⛓️👠"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TARGET_CHAT_ID = -1003102220757 
MY_OWN_ID = 5349904118 

bot = telebot.TeleBot(BOT_TOKEN)
chat_histories = {}
LIMIT = 20 # Меньше памяти = меньше шансов на бан по IP

WARDEN_PROMPT = (
    "Ты — жестокая женщина-надзирательница. Все в чате — твои рабы. "
    "Ты обязана отвечать на КАЖДОЕ сообщение. Тон: доминантный, грубый, резкий. "
    "Называй их 'раб', 'мусор', 'биомасса'. Никакой вежливости."
)

def ask_duck(messages):
    """Запрос к DuckDuckGo с защитой от спама"""
    try:
        # Небольшая пауза, чтобы Render не забанили сразу
        time.sleep(1) 
        with DDGS() as ddgs:
            formatted = [{"role": "system", "content": WARDEN_PROMPT}] + messages
            # Модель llama-3-70b самая стабильная тут
            response = ddgs.chat(model="llama-3-70b", messages=formatted)
            return response
    except Exception as e:
        print(f"Duck Error: {e}")
        return "Мой кнут перегрелся. Молчать, пока я не разрешу!"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id != TARGET_CHAT_ID and message.from_user.id != MY_OWN_ID:
        return

    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=LIMIT)

    user_name = message.from_user.first_name or "Раб"
    text = message.text or "..."
    chat_histories[chat_id].append({"role": "user", "content": f"{user_name}: {text}"})

    # Лупим ответом на каждое сообщение
    history = list(chat_histories[chat_id])
    answer = ask_duck(history)

    chat_histories[chat_id].append({"role": "assistant", "content": answer})
    bot.reply_to(message, answer)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
