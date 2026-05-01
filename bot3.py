import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

DB_NAME = "bot.db"
ADMIN_ID = 7983340250

logging.basicConfig(level=logging.INFO)

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS channels (user_id INT, chat_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS posts (user_id INT, type TEXT, fid TEXT, cap TEXT, txt TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS setting (user_id INT PRIMARY KEY, interval INT, last INT, pause INT)')
    conn.commit()
    conn.close()

init_db()

def get_kb(uid):
    conn = get_db()
    row = conn.execute("SELECT pause FROM setting WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    p = "▶️ استئناف" if (row and row[0]) else "⏸ ايقاف"
    kb = [
        [InlineKeyboardButton("➕ قناة", callback_data="ch"), InlineKeyboardButton("➕ منشور", callback_data="post")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list"), InlineKeyboardButton("📊 حالة", callback_data="stat")],
        [InlineKeyboardButton("⏱ فاصل", callback_data="int"), InlineKeyboardButton(p, callback_data="pause")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="del")]
    ]
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    uid = update.effective_user.id
    await update.message.reply_text("🔧 بوت النشر", reply_markup=get_kb(uid))

async def callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    if query.data == "ch":
        await query.edit_message_text("ارسل معرف القناة:")
        context.user_data['action'] = 'add_ch'
    elif query.data == "post":
        await query.edit_message_text("ارسل المنشور:")
        context.user_data['action'] = 'add_post'
    elif query.data == "int":
        await query.edit_message_text("ارسل عدد الدقائق:")
        context.user_data['action'] = 'set_int'
    elif query.data == "del":
        await query.edit_message_text("ارسل معرف القناة للحذف:")
        context.user_data['action'] = 'del_ch'
    elif query.data == "list":
        conn = get_db()
        chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        conn.close()
        txt = "\n".join([f"• {r[0]}" for r in chs]) if chs else "لا توجد قنوات"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu")]]))
    elif query.data == "stat":
        conn = get_db()
        pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        cc = conn.execute("SELECT COUNT(*) FROM channels WHERE user_id=?", (uid,)).fetchone()[0]
        conn.close()
        await query.edit_message_text(f"📦 منشورات: {pc}\n📢 قنوات: {cc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu")]]))
    elif query.data == "pause":
        conn = get_db()
        conn.execute("INSERT INTO setting (user_id, pause) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET pause = 1 - pause", (uid,))
        conn.commit()
        conn.close()
        await start(update, context)
    elif query.data == "menu":
        await start(update, context)

async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text
    action = context.user_data.get('action')
    conn = get_db()
    
    if action == 'add_ch':
        conn.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)", (uid, text))
        await update.message.reply_text(f"✅ تم اضافة {text}")
    elif action == 'del_ch':
        conn.execute("DELETE FROM channels WHERE user_id=? AND chat_id=?", (uid, text))
        await update.message.reply_text("✅ تم الحذف" if conn.total_changes else "⚠️ غير موجود")
    elif action == 'set_int':
        if text.isdigit() and 1 <= int(text) <= 1440:
            conn.execute("INSERT INTO setting (user_id, interval) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET interval=?", (uid, int(text), int(text)))
            await update.message.reply_text(f"⏱ تم ضبط الفاصل {text} دقيقة")
        else:
            await update.message.reply_text("⚠️ ارسل رقم بين 1 و 1440")
    elif action == 'add_post':
        if update.message.photo:
            t, fid, cap = "photo", update.message.photo[-1].file_id, update.message.caption
        elif update.message.video:
            t, fid, cap = "video", update.message.video.file_id, update.message.caption
        elif update.message.document:
            t, fid, cap = "document", update.message.document.file_id, update.message.caption
        elif update.message.audio:
            t, fid, cap = "audio", update.message.audio.file_id, update.message.caption
        elif update.message.voice:
            t, fid, cap = "voice", update.message.voice.file_id, update.message.caption
        elif update.message.sticker:
            t, fid = "sticker", update.message.sticker.file_id
            cap = None
        else:
            t, fid, cap = "text", None, text
        conn.execute("INSERT INTO posts (user_id, type, fid, cap, txt) VALUES (?, ?, ?, ?, ?)", (uid, t, fid, cap, text if t=="text" else None))
        await update.message.reply_text("✅ تم حفظ المنشور")
    
    conn.commit()
    conn.close()
    context.user_data['action'] = None
    await start(update, context)

async def auto_post(app):
    while True:
        try:
            now = int(time.time())
            conn = get_db()
            users = conn.execute("SELECT user_id, interval FROM setting WHERE (? - last) >= (interval*60) AND pause = 0", (now,)).fetchall()
            for uid, interval in users:
                channels = [r[0] for r in conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()]
                if not channels: continue
                post = conn.execute("SELECT type, fid, cap, txt FROM posts WHERE user_id=? ORDER BY RANDOM() LIMIT 1", (uid,)).fetchone()
                if not post: continue
                conn.execute("UPDATE setting SET last=? WHERE user_id=?", (now, uid))
                conn.commit()
                t, fid, cap, txt = post
                for ch in channels:
                    try:
                        if t == "text": await app.bot.send_message(ch, text=txt)
                        elif t == "photo": await app.bot.send_photo(ch, photo=fid, caption=cap)
                        elif t == "video": await app.bot.send_video(ch, video=fid, caption=cap)
                        elif t == "document": await app.bot.send_document(ch, document=fid, caption=cap)
                        elif t == "audio": await app.bot.send_audio(ch, audio=fid, caption=cap)
                        elif t == "voice": await app.bot.send_voice(ch, voice=fid, caption=cap)
                        elif t == "sticker": await app.bot.send_sticker(ch, sticker=fid)
                    except: pass
            conn.close()
        except: pass
        await asyncio.sleep(30)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL, handle_text))
    asyncio.create_task(auto_post(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
