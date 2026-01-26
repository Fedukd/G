import os
import telebot
import requests
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

# --- НАСТРОЙКИ (Берем всё из переменных окружения) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
SCREENSHOT_API_KEY = os.environ.get('SCREENSHOT_API_KEY') # Теперь берется отсюда!

ADMIN_PASSWORD = "1234sezer1234"
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

# --- ФУНКЦИЯ СКРИНШОТА ---
@bot.message_handler(commands=['screen'])
def take_screenshot(message):
    if message.chat.id not in ALLOWED_CHATS or IS_MAINTENANCE: return
    
    if not SCREENSHOT_API_KEY:
        bot.reply_to(message, "❌ API ключ для скриншотов не настроен в переменных окружения Render.")
        return

    try:
        url = message.text.split(maxsplit=1)[1]
        if not url.startswith('http'):
            url = 'https://' + url
    except IndexError:
        bot.reply_to(message, "⚠️ Напиши ссылку, например: `/screen google.com`", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "📸 Захожу на сайт и делаю снимок...")

    api_url = f"https://api.screenshotmachine.com/?key={SCREENSHOT_API_KEY}&url={url}&dimension=1920x1080&format=jpg"
    
    try:
        response = requests.get(api_url, timeout=20)
        if response.status_code == 200:
            bot.send_photo(message.chat.id, response.content, caption=f"✅ Скриншот готов: {url}")
            bot.delete_message(message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text(f"❌ Ошибка API ({response.status_code}). Проверь ключ в настройках Render.", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", message.chat.id, status_msg.message_id)

# --- АДМИН-ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin_auth(message):
    if message.from_user.id != MY_OWN_ID: return
    msg = bot.send_message(message.chat.id, "🔐 Введите пароль администратора:")
    bot.register_next_step_handler(msg, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        show_admin_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ Неверный пароль.")

def show_admin_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    status_btn = "🔴 Выключить бота" if not IS_MAINTENANCE else "🟢 Включить бота"
    markup.add("📊 Статус", status_btn)
    markup.add("➕ Добавить чат", "🧹 Очистить всё")
    markup.add("🚪 Выход")
    bot.send_message(chat_id, "⚙️ Админ-панель открыта:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["🔴 Выключить бота", "🟢 Включить бота"])
def toggle_maintenance(message):
    if message.from_user.id != MY_OWN_ID: return
    global IS_MAINTENANCE
    IS_MAINTENANCE = not IS_MAINTENANCE
    state = "ВКЛЮЧЕН" if IS_MAINTENANCE else "ВЫКЛЮЧЕН"
    bot.send_message(message.chat.id, f"🛠 Режим тех. перерыва: **{state}**", parse_mode="Markdown")
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "📊 Статус")
def admin_status(message):
    if message.from_user.id != MY_OWN_ID: return
    mode = "🔴 Пауза" if IS_MAINTENANCE else "🟢 Работает"
    status_text = (
        f"⚙️ Режим: {mode}\n"
        f"👥 Чатов в списке: {len(ALLOWED_CHATS)}\n"
        f"🧠 Активных диалогов: {len(chat_histories)}"
    )
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: message.text == "➕ Добавить чат")
def ask_chat_id(message):
    if message.from_user.id != MY_OWN_ID: return
    msg = bot.send_message(message.chat.id, "Пришли ID чата (числом):")
    bot.register_next_step_handler(msg, add_chat_to_list)

def add_chat_to_list(message):
    try:
        new_id = int(message.text)
        if new_id not in ALLOWED_CHATS:
            ALLOWED_CHATS.append(new_id)
            bot.send_message(message.chat.id, f"✅ Чат {new_id} добавлен.")
        else:
            bot.send_message(message.chat.id, "Уже есть в списке.")
    except: bot.send_message(message.chat.id, "Ошибка.")

@bot.message_handler(func=lambda message: message.text == "🧹 Очистить всё")
def clear_all(message):
    if message.from_user.id != MY_OWN_ID: return
    chat_histories.clear()
    bot.send_message(message.chat.id, "🧹 Память всех чатов стерта.")

@bot.message_handler(func=lambda message: message.text == "🚪 Выход")
def admin_exit(message):
    bot.send_message(message.chat.id, "Админка закрыта.", reply_markup=types.ReplyKeyboardRemove())

# --- НАСТРОЙКИ ЧАТА ---
@bot.message_handler(commands=['settings'])
def show_settings(message):
    if message.chat.id not in ALLOWED_CHATS or IS_MAINTENANCE: return
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_mem = types.InlineKeyboardButton("🧠 Память", callback_data="menu_memory")
    btn_mod = types.InlineKeyboardButton("🤖 Модель", callback_data="menu_model")
    markup.add(btn_mem, btn_mod)
    bot.send_message(message.chat.id, "⚙️ Настройки чата:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    if call.data == "menu_memory":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⌨️ Свое число", callback_data="limit_custom"))
        bot.edit_message_text("Введи лимит сообщений (0-2000):", chat_id, call.message.message_id, reply_markup=markup)
    elif call.data == "menu_model":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for name in MODELS.keys():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"setmod_{name}"))
        bot.edit_message_text("Выбери модель:", chat_id, call.message.message_id, reply_markup=markup)
    elif call.data.startswith("setmod_"):
        model_name = call.data.split("_")[1]
        chat_models[chat_id] = model_name
        bot.edit_message_text(f"✅ Модель: {model_name}", chat_id, call.message.message_id)
    elif call.data == "limit_custom":
        msg = bot.send_message(chat_id, "Сколько сообщений помнить?")
        bot.register_next_step_handler(msg, process_custom_limit)

def process_custom_limit(message):
    try:
        new_limit = int(message.text)
        if 0 <= new_limit <= 2000:
            chat_id = message.chat.id
            chat_limits[chat_id] = new_limit
            chat_histories[chat_id] = deque(list(chat_histories.get(chat_id, [])), maxlen=new_limit)
            bot.reply_to(message, f"✅ Память: {new_limit}")
        else: bot.reply_to(message, "0-2000!")
    except: bot.reply_to(message, "Ошибка.")

# --- ЛОГИКА ИИ ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in ALLOWED_CHATS: return
    if IS_MAINTENANCE and message.from_user.id != MY_OWN_ID:
        bot.reply_to(message, "🛠 Бот на тех. обслуживании.")
        return

    bot_info = bot.get_me()
    bot_username = f"@{bot_info.username}"
    is_private = message.chat.type == 'private'
    is_reply_to_bot = (message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id)
    is_mentioned = message.text and bot_username in message.text

    if is_private or is_reply_to_bot or is_mentioned:
        limit = chat_limits.get(chat_id, 1000)
        model_alias = chat_models.get(chat_id, "Llama 3.3 70B")
        model_id = MODELS.get(model_alias, "llama-3.3-70b-versatile")
        
        if chat_id not in chat_histories: chat_histories[chat_id] = deque(maxlen=limit)
        clean_text = message.text.replace(bot_username, "").strip() if message.text else ""
        if not clean_text: return

        if limit > 0:
            chat_histories[chat_id].append({"role": "user", "content": clean_text})
            messages_for_ai = list(chat_histories[chat_id])
        else: messages_for_ai = [{"role": "user", "content": clean_text}]

        try:
            completion = client.chat.completions.create(model=model_id, messages=messages_for_ai, temperature=0.7)
            res = completion.choices[0].message.content
            if limit > 0: chat_histories[chat_id].append({"role": "assistant", "content": res})
            bot.reply_to(message, res)
        except Exception as e: print(f"API Error: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)