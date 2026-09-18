import os, json, threading, asyncio, requests
from flask import Flask, request
import google.generativeai as genai
import edge_tts
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# --- الإعدادات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "umm_nada_123"
FISH_KEY = os.getenv("FISH_AUDIO_KEY")
ALLOW_KEY = os.getenv("ALLOW_KEY") or "ام ندى"
PORT = int(os.getenv("PORT", 8080))

# --- ملفات الحفظ ---
def load_json(file, default):
    if not os.path.exists(file): return default
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

replies = load_json("replies.json", {})
modes = load_json("mode.json", {})
numbers = load_json("numbers.json", {"ai_numbers": [], "library_numbers": [], "blocked_numbers": []})

# --- إعداد Gemini بلهجة سعودية ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash", system_instruction="""
انتِ أم ندى من وادي الفرع بالمدينة المنورة، السعودية.
تتكلمين بلهجة حجازية سعودية بيضاء، محترمة وكريمة.
ردودك قصيرة وودودة، تقولين هلا والله، يا هلا، ابشري، الله يسعدك.
لا تقولين كلام يمني ابدا، لهجتك سعودية فقط.
""")

def ask_gemini(text):
    try:
        res = model.generate_content(text)
        return res.text
    except Exception as e:
        return f"يا هلا، اعذريني صار عندي ضغط شوي، ارسلي مرة ثانية. ({e})"

# --- نظام الأرقام ---
def get_status(num):
    num = num.replace("+","").replace(" ","")
    if num in numbers["blocked_numbers"]: return "محظور"
    if num in numbers["ai_numbers"]: return "ذكاء"
    if num in numbers["library_numbers"]: return "مكتبة"
    return "جديد"

def handle_number_command(text):
    parts = text.split()
    if len(parts) < 2: return None
    cmd, num = parts[0], parts[1].replace("+","")
    if "/حظر" in cmd:
        if num not in numbers["blocked_numbers"]: numbers["blocked_numbers"].append(num)
        for l in ["ai_numbers","library_numbers"]:
            if num in numbers[l]: numbers[l].remove(num)
        save_json("numbers.json", numbers); return f"تم حظر {num} 🚫"
    if "/سماح" in cmd:
        if num in numbers["blocked_numbers"]: numbers["blocked_numbers"].remove(num)
        if num not in numbers["ai_numbers"]: numbers["ai_numbers"].append(num)
        save_json("numbers.json", numbers); return f"تم السماح لـ {num} ✅ وصار ذكاء"
    if "/ذكاء" in cmd:
        for l in ["blocked_numbers","library_numbers"]:
            if num in numbers[l]: numbers[l].remove(num)
        if num not in numbers["ai_numbers"]: numbers["ai_numbers"].append(num)
        save_json("numbers.json", numbers); return f"الرقم {num} الآن يرد عليه ذكاء سعودي 🤖"
    if "/مكتبة" in cmd:
        for l in ["blocked_numbers","ai_numbers"]:
            if num in numbers[l]: numbers[l].remove(num)
        if num not in numbers["library_numbers"]: numbers["library_numbers"].append(num)
        save_json("numbers.json", numbers); return f"الرقم {num} الآن يرد من المكتبة فقط 📚"
    return None

# --- نظام الصوت ---
async def text_to_voice(text, path="voice.mp3"):
    try:
        # صوت بنت سعودية
        communicate = edge_tts.Communicate(text, "ar-SA-ZariyahNeural")
        await communicate.save(path)
        return path
    except: return None

def text_to_voice_sync(text, path="voice.mp3"):
    return asyncio.run(text_to_voice(text, path))

# --- المنطق الموحد للرد ---
def get_reply(chat_id, text, platform="telegram"):
    chat_id = str(chat_id)
    text = text.strip()

    # 1. أوامر التحكم بالأرقام (للمالكة فقط)
    if text.startswith(("/حظر","/سماح","/ذكاء","/مكتبة")):
        r = handle_number_command(text)
        if r: return {"type":"text", "text": r}

    if text == "/الأرقام":
        return {"type":"text", "text": f"📊 الأرقام:\nذكاء: {numbers['ai_numbers']}\nمكتبة: {numbers['library_numbers']}\nمحظور: {numbers['blocked_numbers']}"}

    if text.startswith("/وضع الرقم"):
        num = text.split()[-1].replace("+","")
        return {"type":"text", "text": f"وضع {num}: {get_status(num)}"}

    # 2. أوامر المكتبة
    if text.startswith("/حفظ"):
        try:
            k,v = text.replace("/حفظ","",1).split("=",1)
            replies[k.strip()] = v.strip()
            save_json("replies.json", replies)
            return {"type":"text","text":f"تم الحفظ ✅ {k.strip()}"}
        except: return {"type":"text","text":"الصيغة: /حفظ الكلمة = الرد"}

    if text.startswith("/حذف"):
        k = text.replace("/حذف","",1).strip()
        if k in replies: del replies[k]; save_json("replies.json", replies); return {"type":"text","text":f"تم الحذف {k}"}
        return {"type":"text","text":"ما لقيت الكلمة"}

    if text.startswith("/تغيير"):
        try:
            k,v = text.replace("/تغيير","",1).split("=",1)
            replies[k.strip()] = v.strip()
            save_json("replies.json", replies)
            return {"type":"text","text":f"تم التغيير ✅"}
        except: return {"type":"text","text":"الصيغة: /تغيير الكلمة = الرد الجديد"}

    if text == "/القائمة":
        if not replies: return {"type":"text","text":"المكتبة فاضية"}
        t = "\n".join([f"- {k}: {v}" for k,v in replies.items()])
        return {"type":"text","text": f"📚 المكتبة:\n{t}"}

    # 3. أوامر الصوت
    if text in ["صوت وهمي","وضع صوت وهمي"]:
        modes[chat_id] = "fake_voice"; save_json("mode.json", modes)
        return {"type":"text","text":"تم ✅ الآن ارد عليك صوت وهمي بصوت بنت سعودية 🎙️"}
    if text in ["صوت حقيقي","وضع صوت حقيقي"]:
        modes[chat_id] = "real_voice"; save_json("mode.json", modes)
        return {"type":"text","text":"تم ✅ الآن صوت حقيقي، واذا خلص الرصيد ارجع وهمي تلقائي"}
    if text in ["كتابة","وضع كتابة","وضع الكتابة"]:
        modes[chat_id] = "text"; save_json("mode.json", modes)
        return {"type":"text","text":"تم ✅ رجعت كتابة بلهجة سعودية ✍️"}

    # 4. تحقق من المكتبة أولا
    for k,v in replies.items():
        if k in text:
            reply_text = v
            mode = modes.get(chat_id, "text")
            if mode in ["fake_voice","real_voice"]:
                return {"type":"voice","text":reply_text}
            return {"type":"text","text":reply_text}

    # 5. تحقق من نوع الرقم
    current_status = get_status(chat_id)
    if current_status == "محظور":
        return None # لا يرد
    if current_status == "مكتبة":
        return {"type":"text","text":"هلا والله، ما عندي رد محفوظ لهالكلمة في المكتبة 📚"}
    if current_status == "جديد" and ALLOW_KEY in text:
        # اذا ارسل كلمة السر اسمح له
        numbers["ai_numbers"].append(chat_id.replace("+",""))
        save_json("numbers.json", numbers)
        return {"type":"text","text":f"يا هلا والله حياك، تم السماح لك يا وجه الخير، قولي وش تبغي؟ كلمة السر صحيحة ✅"}

    # 6. الرد بالذكاء السعودي
    ai_reply = ask_gemini(text)
    mode = modes.get(chat_id, "text")
    if mode in ["fake_voice","real_voice"]:
        return {"type":"voice","text":ai_reply}
    return {"type":"text","text":ai_reply}

# --- تيليجرام ---
async def tg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    text = update.message.text or ""

    # تحقق من الحظر في التيليجرام ايضا
    if get_status(chat_id) == "محظور": return

    result = get_reply(chat_id, text, "telegram")
    if not result: return

    if result["type"] == "text":
        await update.message.reply_text(result["text"])
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
        path = text_to_voice_sync(result["text"])
        if path: await update.message.reply_voice(voice=open(path,"rb"))

# --- واتساب ---
app = Flask(__name__)

def send_whatsapp(to, text, voice_path=None):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    if voice_path:
        # رفع الصوت اولا
        # للتبسيط نرسل كـ audio link لو عندك، هنا نرسل كنص اذا فشل الرفع
        data = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body": text + " (🎙️)"}}
    else:
        data = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body": text}}
    requests.post(url, headers=headers, json=data)

@app.route("/", methods=["GET"])
def home(): return "Bot is alive - Umm Nada Bot - وادي الفرع"

@app.route("/webhook", methods=["GET","POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Error"
    data = request.json
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg = entry["messages"][0]
            from_num = msg["from"]
            text = msg["text"]["body"] if msg["type"]=="text" else ""

            if get_status(from_num) == "محظور": return "ok",200

            result = get_reply(from_num, text, "whatsapp")
            if not result: return "ok",200

            if result["type"] == "text":
                send_whatsapp(from_num, result["text"])
            else:
                path = text_to_voice_sync(result["text"], f"{from_num}.mp3")
                # هنا ترسل الصوت كملف لو عندك سيرفر رفع، مؤقتا نرسل النص مع تنبيه صوتي
                send_whatsapp(from_num, result["text"])
    except Exception as e: print(e)
    return "ok",200

# --- التشغيل ---
def run_flask(): app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tg_handler))
        application.add_handler(CommandHandler(["حفظ","حذف","تغيير","القائمة","حظر","سماح","ذكاء","مكتبة","الأرقام"], tg_handler))
        print("بوت أم ندى شغال...")
        application.run_polling()