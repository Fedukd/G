import os
import telebot
from groq import Groq
from collections import deque
from flask import Flask
from threading import Thread

# --- Веб-сервер для обмана Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Status: Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# Список разрешенных групп
ALLOWED_CHATS = [-1002322741739, -1003102220757]
chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    
    # 1. Если это группа, проверяем, разрешена ли она
    if chat_id < 0 and chat_id not in ALLOWED_CHATS:
        return

    # Получаем инфо о боте
    bot_info = bot.get_me()
    bot_username = f"@{bot_info.username}"

    # Проверки для групп
    is_mentioned = message.text and bot_username in message.text
    is_reply_to_bot = (message.reply_to_message and 
                       message.reply_to_message.from_user.id == bot_info.id)

    # 2. Логика ответа:
    # Если это личка (chat_id > 0) — отвечаем всегда.
    # Если это группа — только если упомянули или ответили на сообщение бота.
    if chat_id < 0 and not (is_mentioned or is_reply_to_bot):
        return

    # Инициализация истории
    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=15)

    # Чистим текст
    text_to_send = message.text.replace(bot_username, "").strip() if message.text else ""
    if not text_to_send:
        return

    chat_histories[chat_id].append({"role": "user", "content": text_to_send})

    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=list(chat_histories[chat_id]),
            temperature=0.7
        )

        response_text = completion.choices[0].message.content
        chat_histories[chat_id].append({"role": "assistant", "content": response_text})

        bot.reply_to(message, response_text)

    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    # Запуск Flask
    Thread(target=run_flask, daemon=True).start()
    print("✅ Flask Server Started")
    
    # Запуск Бота
    print("✅ Telegram Bot Started")
    bot.polling(none_stop=True)
