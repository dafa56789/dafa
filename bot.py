
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from openai import OpenAI

from database import init_db
from memory import save_memory, get_memories

# ===== LOAD ENV =====
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== SHORT TERM MEMORY =====
user_histories = {}

SYSTEM_PROMPT = """
Bạn là AI có trí nhớ dài hạn.
Khi có thông tin về user (tên, sở thích, công việc...), hãy ghi nhớ.
Sử dụng thông tin cũ nếu liên quan.
"""

# ===== CHAT =====
async def chat(update: Update, user_id: int, text: str):
    # short-term
    if user_id not in user_histories:
        user_histories[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    # long-term
    memories = get_memories(user_id)
    memory_text = "\n".join(memories)

    user_histories[user_id].append({
        "role": "user",
        "content": f"""
Tin nhắn hiện tại: {text}

Thông tin bạn biết về user:
{memory_text}
"""
    })

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=user_histories[user_id],
    )

    reply = response.choices[0].message.content

    user_histories[user_id].append({
        "role": "assistant",
        "content": reply
    })

    # lưu memory quan trọng
    if "tôi là" in text.lower() or "tên tôi" in text.lower():
        save_memory(user_id, text)

    return reply


# ===== HANDLER =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    reply = await chat(update, user_id, text)
    await update.message.reply_text(reply)


# ===== RESET =====
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Đã reset memory ngắn hạn.")


# ===== MAIN =====
init_db()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT, handle))

print("🚀 Bot running...")
app.run_polling()
