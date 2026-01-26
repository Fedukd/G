import os
import telebot
from groq import Groq
from collections import deque
from flask import Flask
from threading import Thread

# --- Веб-сервер для Render ---
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

# Твой ID и ID групп
ALLOWED_CHATS = [5349904118, -100232274173, -100310222075]

# Память: помнит последние 1000 сообщений
chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    
    # Проверка доступа
    if chat_id not in ALLOWED_CHATS:
        return

    bot_info = bot.get_me()
    bot_username = f"@{bot_info.username}"

    is_private = message.chat.type == 'private'
    is_reply_to_bot = (message.reply_to_message and 
                       message.reply_to_message.from_user.id == bot_info.id)
    is_mentioned = message.text and bot_username in message.text

    # Отвечаем в личке или если позвали в группе
    if is_private or is_reply_to_bot or is_mentioned:
        
        if chat_id not in chat_histories:
            chat_histories[chat_id] = deque(maxlen=1000)

        clean_text = message.text.replace(bot_username, "").strip() if message.text else ""
        if not clean_text:
            return

        chat_histories[chat_id].append({"role": "user", "content": clean_text})

        try:
            # Теперь отправляем только историю без грубого промпта
            messages_for_ai = list(chat_histories[chat_id])

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_for_ai,
                temperature=0.7,
                max_tokens=1024
            )

            response_text = completion.choices[0].message.content
            chat_histories[chat_id].append({"role": "assistant", "content": response_text})

            bot.reply_to(message, response_text)

        except Exception as e:
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    print("✅ Бот запущен.")
    bot.polling(none_stop=True)
