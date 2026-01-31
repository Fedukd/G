import os
import re
import psycopg2
from collections import Counter
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq

# --- НАСТРОЙКИ ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Твой ID, который ты добавишь в Render
ALLOWED_ID = int(os.getenv("MY_ID", 0)) 

bot = Client("fanstat_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# Логируем всё (это можно оставить для всех, чтобы база росла)
@bot.on_message(filters.group & filters.text)
async def logger(client, message):
    if message.from_user:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user_id, text) VALUES (%s, %s)", 
                    (message.from_user.id, message.text))
        conn.commit()
        cur.close()
        conn.close()

# А вот команды и кнопки — ТОЛЬКО ДЛЯ ТЕБЯ
@bot.on_message(filters.command("start") & filters.user(ALLOWED_ID))
async def start(client, message):
    await message.reply("Доступ разрешен. Твой личный Телелог готов:", reply_markup=main_kb())

@bot.on_callback_query()
async def callbacks(client, callback_query):
    # Проверка: если нажал не ты — бот просто проигнорит или пошлет
    if callback_query.from_user.id != ALLOWED_ID:
        await callback_query.answer("Доступ закрыт. Это личный бот.", show_alert=True)
        return

    uid = callback_query.from_user.id
    conn = get_conn()
    cur = conn.cursor()

    if callback_query.data == "words":
        cur.execute("SELECT text FROM messages WHERE user_id = %s LIMIT 5000", (uid,))
        rows = cur.fetchall()
        text = " ".join([r[0] for r in rows if r[0]]).lower()
        words = re.findall(r'[а-яёa-z]{3,}', text)
        top = Counter(words).most_common(10)
        res = "**Топ слов:**\n" + "\n".join([f"— {c} {w}" for w, c in top])
        await callback_query.edit_message_text(res, reply_markup=main_kb())

    elif callback_query.data == "ai":
        await callback_query.answer("Groq думает...")
        cur.execute("SELECT text FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 50", (uid,))
        recent = [r[0] for r in cur.fetchall()]
        
        chat = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Ты дерзкий аналитик логов. Опиши психотип юзера по сообщениям."},
                      {"role": "user", "content": "\n".join(recent)}]
        )
        await callback_query.edit_message_text(f"**Анализ ИИ:**\n{chat.choices[0].message.content}", reply_markup=main_kb())

    cur.close()
    conn.close()

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Профиль", callback_data="st"), InlineKeyboardButton("🔔 Следить", callback_data="tr")],
        [InlineKeyboardButton("💬 Сообщения", callback_data="msg"), InlineKeyboardButton("🔎 Анализ", callback_data="ai")],
        [InlineKeyboardButton("🗣 Частота слов", callback_data="words")]
    ])

if __name__ == "__main__":
    bot.run()
