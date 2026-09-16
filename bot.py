import os, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio, edge_tts
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

REPLIES = {
 "مساء الخير": "مساء الورد يا حبيب قلبي نبهان",
 "صباح الخير": "صباح العسل"
}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
def run_server():
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

async def make_voice(text):
    path = "/tmp/voice.mp3"
    comm = edge_tts.Communicate(text, voice="ar-SA-ZariyahNeural")
    await comm.save(path)
    return path

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    txt = update.message.text
    final = txt
    for k,v in REPLIES.items():
        if k in txt: final = v; break
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
    p = await make_voice(final)
    await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(p,"rb"))

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()
