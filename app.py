import os
import telebot
from groq import Groq
from collections import deque
from flask import Flask
from threading import Thread

# --- Инициализация веб-сервера для Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render передает порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Настройки бота ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# Список разрешенных ID групп
ALLOWED_CHATS = [-1002322741739, -1003102220757]

# Хранилище контекста для каждой группы
chat_histories = {}

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id

    # 1. Проверка: чат должен быть в списке разрешенных
    if chat_id not in ALLOWED_CHATS:
        return

    # Получаем юзернейм бота
    bot_info = bot.get_me()
    bot_username = f"@{bot_info.username}"

    # 2. Проверка: упомянули ли бота или ответили ли на его сообщение
    is_mentioned = message.text and bot_username in message.text
    is_reply_to_bot = (message.reply_to_message and 
                       message.reply_to_message.from_user.id == bot_info.id)

    # Если это группа (chat_id < 0) и бота не звали — игнорируем
    if chat_id < 0 and not (is_mentioned or is_reply_to_bot):
        return

    # Инициализируем историю для группы
    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=20) # Ограничим историю 20 сообщениями для экономии памяти

    # Чистим текст сообщения от упоминания бота
    clean_text = message.text.replace(bot_username, "").strip() if message.text else ""
    if not clean_text:
        return

    chat_histories[chat_id].append({"role": "user", "content": clean_text})

    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=list(chat_histories[chat_id]),
            temperature=0.7,
            max_tokens=1024
        )

        response_text = completion.choices[0].message.content
        chat_histories[chat_id].append({"role": "assistant", "content": response_text})

        # Отвечаем реплаем
        bot.reply_to(message, response_text)

    except Exception as e:
        print(f"Ошибка в группе {chat_id}: {e}")

if __name__ == "__main__":
    # 1. Сначала запускаем Flask в фоновом потоке
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    print("🚀 Flask запущен для Render!")
    
    # 2. Затем запускаем самого бота
    print("🤖 Бот с фильтром упоминаний запущен!")
    bot.polling(none_stop=True)
