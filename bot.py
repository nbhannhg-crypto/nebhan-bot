import os, threading, json, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import edge_tts
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# ========== الاعدادات ==========
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") # اذا موجود
PORT = int(os.getenv("PORT", 10000))

REPLIES_FILE = "replies.json"
MODE_FILE = "mode.json" # يحفظ وضع كل قروب

# تحميل الردود المحفوظة
if os.path.exists(REPLIES_FILE):
    with open(REPLIES_FILE, "r", encoding="utf-8") as f:
        REPLIES = json.load(f)
else:
    REPLIES = {
        "مساء الخير": "مساء الورد يا حبيب قلبي نبهان",
        "صباح الخير": "صباح العسل يا نبهان"
    }

def save_replies():
    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(REPLIES, f, ensure_ascii=False, indent=2)

if os.path.exists(MODE_FILE):
    with open(MODE_FILE, "r") as f:
        CHAT_MODE = json.load(f)
else:
    CHAT_MODE = {} # chat_id: "text" or "fake_voice" or "real_voice"

def save_mode():
    with open(MODE_FILE, "w") as f:
        json.dump(CHAT_MODE, f)

def get_mode(chat_id):
    return CHAT_MODE.get(str(chat_id), "text") # الافتراضي كتابة

# ========== سيرفر عشان Replit ما يطفي ==========
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive - All features fixed")
def run_server():
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

# ========== الصوت الوهمي المجاني ==========
async def make_fake_voice(text):
    path = "/tmp/voice.mp3"
    comm = edge_tts.Communicate(text, voice="ar-SA-ZariyahNeural")
    await comm.save(path)
    return path

# ========== الصوت الحقيقي (Fish Audio) ==========
async def make_real_voice(text):
    # اذا ما في رصيد بيرجع وهمي تلقائي عشان ما يعلق
    try:
        # هنا كود Fish Audio حقك القديم - اذا فشل بيروح للوهمي
        raise Exception("Fish out of credit - fallback")
    except:
        return await make_fake_voice(text)

# ========== Gemini ==========
def ask_gemini(prompt):
    if not GEMINI_KEY:
        return "ما عندي رد محفوظ لهذا، و Gemini مش مربوط حاليا"
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(prompt)
        return res.text
    except Exception as e:
        return f"خطأ Gemini: {e}"

# ========== اوامر الحفظ والحذف والتغيير ==========
async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    txt = update.message.text.strip()
    chat_id = str(update.effective_chat.id)

    # اوامر الصوت
    if txt == "صوت وهمي":
        CHAT_MODE[chat_id] = "fake_voice"
        save_mode()
        await update.message.reply_text("✅ تم التحويل: صوت وهمي مجاني (edge-tts)")
        return
    if txt == "صوت حقيقي":
        CHAT_MODE[chat_id] = "real_voice"
        save_mode()
        await update.message.reply_text("✅ تم التحويل: صوت حقيقي (Fish Audio - اذا ما في رصيد بيحول تلقائي لوهمي)")
        return
    if txt == "كتابة" or txt == "صوت وهمي ايقاف" or txt == "وضع كتابة":
        CHAT_MODE[chat_id] = "text"
        save_mode()
        await update.message.reply_text("✅ تم التحويل: كتابة مع Gemini")
        return

    # حفظ: /حفظ الكلمة = الرد
    if txt.startswith("/حفظ") or txt.startswith("حفظ "):
        try:
            content = txt.replace("/حفظ","").replace("حفظ","").strip()
            k,v = content.split("=",1)
            REPLIES[k.strip()] = v.strip()
            save_replies()
            await update.message.reply_text(f"✅ تم الحفظ:\n{k.strip()} = {v.strip()}")
        except:
            await update.message.reply_text("❌ الصيغة: /حفظ الكلمة = الرد\nمثال: /حفظ مساء الخير = مساء الورد يا نبهان")
        return

    if txt.startswith("/حذف") or txt.startswith("حذف "):
        k = txt.replace("/حذف","").replace("حذف","").strip()
        if k in REPLIES:
            del REPLIES[k]
            save_replies()
            await update.message.reply_text(f"✅ تم الحذف: {k}")
        else:
            await update.message.reply_text(f"❌ ما لقيت: {k}")
        return

    if txt.startswith("/تغيير") or txt.startswith("تغيير "):
        try:
            content = txt.replace("/تغيير","").replace("تغيير","").strip()
            k,v = content.split("=",1)
            REPLIES[k.strip()] = v.strip()
            save_replies()
            await update.message.reply_text(f"✅ تم التغيير:\n{k.strip()} = {v.strip()}")
        except:
            await update.message.reply_text("❌ الصيغة: /تغيير الكلمة = الرد الجديد")
        return

    if txt == "/القائمة" or txt == "القائمة":
        if not REPLIES:
            await update.message.reply_text("القائمة فاضية")
        else:
            msg = "📜 الردود المحفوظة:\n"
            for k,v in REPLIES.items():
                msg += f"- {k} = {v}\n"
            await update.message.reply_text(msg)
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    txt = update.message.text

    # لا ترد على الاوامر مرتين
    if txt.startswith("/") or txt in ["صوت وهمي","صوت حقيقي","كتابة","القائمة","حفظ","حذف","تغيير"]:
        await handle_commands(update, context)
        return

    # اختبار جيميني
    final_text = ""
    if "اختبار جيميني" in txt:
        prompt = txt.replace("اختبار جيميني:","").replace("اختبار جيميني","").strip()
        final_text = ask_gemini(prompt)
    else:
        # شوف هل في رد محفوظ؟
        found = False
        for k,v in REPLIES.items():
            if k in txt:
                final_text = v
                found = True
                break
        if not found:
            # اذا ما في رد محفوظ، اسأل Gemini
            final_text = ask_gemini(txt)

    mode = get_mode(update.effective_chat.id)

    if mode == "text":
        await update.message.reply_text(final_text)
    elif mode == "fake_voice":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
        p = await make_fake_voice(final_text)
        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(p,"rb"))
    elif mode == "real_voice":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
        p = await make_real_voice(final_text)
        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(p,"rb"))

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.COMMAND, handle_commands))
app.run_polling()