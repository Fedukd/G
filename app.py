import os
import re
import psycopg2
from collections import Counter
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq

# --- Настройки из Render ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ALLOWED_ID = int(os.getenv("MY_ID", 0)) 

bot = Client("fanstat_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# Молча собираем сообщения в группах
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

# Твой личный поиск
@bot.on_message(filters.private & filters.user(ALLOWED_ID) & filters.text)
async def search_handler(client, message):
    query = message.text.strip()
    
    if query.isdigit():
        target_id = int(query)
        try:
            # Тянем инфу напрямую из ТГ
            user = await client.get_users(target_id)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "нет юзернейма"
        except Exception:
            name, username = "Неизвестно", "не найден в контактах"

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages WHERE user_id = %s", (target_id,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()

        res = f"🔍 **Результат по ID {target_id}:**\n"
        res += f"👤 Имя: {name}\n"
        res += f"🔗 Юзер: {username}\n"
        res += f"✉️ Сообщений в базе: `{count}`"
        
        await message.reply(res, reply_markup=main_kb(target_id))
    elif query == "/start":
        await message.reply("Кидай ID чела — выверну его логи наизнанку.", reply_markup=main_kb(ALLOWED_ID))

def main_kb(tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Анализ личности (Groq)", callback_data=f"ai_{tid}")],
        [InlineKeyboardButton("📊 Топ слов", callback_data=f"words_{tid}")]
    ])

@bot.on_callback_query()
async def callbacks(client, callback_query):
    if callback_query.from_user.id != ALLOWED_ID: return
    
    action, tid = callback_query.data.split("_")
    conn = get_conn()
    cur = conn.cursor()

    if action == "words":
        cur.execute("SELECT text FROM messages WHERE user_id = %s LIMIT 3000", (tid,))
        words = re.findall(r'[а-яёa-z]{3,}', " ".join([r[0] for r in cur.fetchall()]).lower())
        top = "\n".join([f"— {c} {w}" for w, c in Counter(words).most_common(10)])
        await callback_query.edit_message_text(f"🗣 **Слова юзера {tid}:**\n{top or 'Мало данных'}", reply_markup=main_kb(tid))

    elif action == "ai":
        await callback_query.answer("Groq анализирует...")
        cur.execute("SELECT text FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 50", (tid,))
        logs = "\n".join([r[0] for r in cur.fetchall()])
        
        if not logs:
            return await callback_query.edit_message_text("❌ Нет сообщений для анализа.", reply_markup=main_kb(tid))

        chat = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Ты жесткий психолог-аналитик. Разбери человека по его сообщениям, не церемонься."},
                      {"role": "user", "content": logs}]
        )
        await callback_query.edit_message_text(f"🧠 **Вердикт ИИ:**\n\n{chat.choices[0].message.content}", reply_markup=main_kb(tid))

    cur.close()
    conn.close()

if __name__ == "__main__":
    bot.run()
