import os
import telebot
from groq import Groq

TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = telebot.TeleBot(TOKEN)
client = Groq(api_key=GROQ_KEY)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": message.text}],
            model="llama-3.3-70b-versatile",
        )
        bot.reply_to(message, completion.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    print("🚀 Бот запущен!")
    bot.infinity_polling()
  
