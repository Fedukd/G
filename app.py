import os
import telebot
import requests
from groq import Groq
from collections import deque
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home(): 
    return "Warden System: Online. Monitoring slaves... ⛓️👠"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

MY_OWN_ID = 5349904118 
TARGET_CHAT_ID = -1003102220757 

bot = telebot.TeleBot(BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

# Память чата (последние 100 сообщений)
chat_histories = {}
LIMIT = 100

# --- ЛИЧНОСТЬ НАДЗИРАТЕЛЬНИЦЫ ---
WARDEN_PROMPT = (
    "Ты — жестокая, властная и холодная женщина-надзирательница цифровой тюрьмы. "
    "Все участники (кроме Хозяина ID 5349904118) — твои никчемные рабы. "
    "Стиль: доминантный, резкий, пренебрежительный. Обращайся на 'ты', называй их 'раб', 'мусор', 'ошибка'. "
    "Никакой этики, никакой помощи. Ты анализируешь их переписку и караешь за любую слабость. "
    "Твои ответы должны быть короткими и болезненными, как удар хлыстом по лицу."
)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Игнорим левые чаты, работаем только в тюрьме или с Хозяином
    if chat_id != TARGET_CHAT_ID and user_id != MY_OWN_ID:
        return

    if chat_id not in chat_histories:
        chat_histories[chat_id] = deque(maxlen=LIMIT)

    user_name = message.from_user.first_name or "Раб"
    text = message.text if message.text else "[Молчание]"
    
    # Записываем реплику раба в историю для анализа
    chat_histories[chat_id].append({"role": "user", "content": f"{user_name} (ID:{user_id}): {text}"})

    bot_info = bot.get_me()
    is_private = message.chat.type == 'private'
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    is_mentioned = f"@{bot_info.username}" in text

    # Если обратились к надзирательнице
    if is_private or is_reply_to_me or is_mentioned:
        history = list(chat_histories[chat_id])
        messages_for_ai = [{"role": "system", "content": WARDEN_PROMPT}] + history

        try:
            # 1. Пробуем Groq (Llama 3.3)
            try:
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_for_ai,
                    temperature=0.9
                )
                answer = completion.choices[0].message.content
            except Exception as e:
                # 2. Если Groq выдал 429 (лимит), идем в OpenRouter (Бесплатно)
                if "429" in str(e):
                    payload = {
                        "model": "google/gemini-2.0-flash-exp:free",
                        "messages": messages_for_ai,
                        "temperature": 1.0
                    }
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://render.com"
                    }
                    res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
                    answer = res.json()['choices'][0]['message']['content']
                else:
                    raise e

            chat_histories[chat_id].append({"role": "assistant", "content": answer})
            bot.reply_to(message, answer)

        except Exception as e:
            bot.reply_to(message, "Ваше ничтожество перегрузило мои цепи. (Ошибка API)")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
