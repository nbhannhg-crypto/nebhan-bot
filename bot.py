import asyncio, os, edge_tts
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

REPLIES = {
 "مساء الخير": "مساء الورد يا حبيب قلبي نبهان",
 "صباح الخير": "صباح العسل"
}

async def make_voice(text):
    path = "/tmp/voice.mp3"
    comm = edge_tts.Communicate(text, voice="ar-SA-ZariyahNeural")
    await comm.save(path)
    return path

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    txt = update.message.text
    final = txt
    for k,v in REPLIES.items():
        if k in txt:
            final = v
            break
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
    p = await make_voice(final)
    await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(p,"rb"))

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
