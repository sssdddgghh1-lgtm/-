import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

DB_NAME = "bot.db"
logging.basicConfig(level=logging.INFO)

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS channels (user_id INT, chat_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS posts (user_id INT, type TEXT, file_id TEXT, cap TEXT, txt TEXT, channel_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS settings (user_id INT PRIMARY KEY, interval INT, last_time INT, paused INT)')
    conn.commit()
    conn.close()

init_db()

async def menu(update, context, is_callback=False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ قناة", callback_data="ch"), InlineKeyboardButton("➕ منشور", callback_data="post")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list"), InlineKeyboardButton("📊 حالة", callback_data="stat")],
        [InlineKeyboardButton("⏱ فاصل", callback_data="int"), InlineKeyboardButton("⏸ ايقاف", callback_data="pause")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="del")]
    ])
    txt = "🔧 بوت النشر الذكي"
    if is_callback:
        await update.callback_query.edit_message_text(txt, reply_markup=kb)
    else:
        await update.message.reply_text(txt, reply_markup=kb)

async def start(update, context):
    await menu(update, context)

async def callback(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data == "list":
        conn = get_db()
        chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        conn.close()
        txt = "\n".join([f"• {r[0]}" for r in chs]) if chs else "لا توجد"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif data == "stat":
        conn = get_db()
        pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        cc = conn.execute("SELECT COUNT(*) FROM channels WHERE user_id=?", (uid,)).fetchone()[0]
        conn.close()
        await q.edit_message_text(f"📦{pc} 📢{cc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif data == "pause":
        conn = get_db()
        conn.execute("INSERT INTO settings (user_id, paused) VALUES (?,1) ON CONFLICT DO UPDATE SET paused=1-paused", (uid,))
        conn.commit()
        conn.close()
        await q.edit_message_text("✅ تم", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif data == "menu":
        await menu(update, context, is_callback=True)
    else:
        # حفظ الحالة
        prompts = {"ch": "ارسل معرف القناة:", "post": "ارسل المنشور:", "int": "ارسل عدد الدقائق:", "del": "ارسل المعرف لحذف القناة:"}
        if data in prompts:
            await q.edit_message_text(prompts[data])
            context.user_data['action'] = data
    return

async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text
    action = context.user_data.get('action')
    conn = get_db()

    if action == "ch":
        conn.execute("INSERT OR IGNORE INTO channels VALUES (?,?)", (uid, text))
        await update.message.reply_text(f"✅ تم اضافة {text}")
    elif action == "del":
        conn.execute("DELETE FROM channels WHERE user_id=? AND chat_id=?", (uid, text))
        await update.message.reply_text("✅ تم الحذف")
    elif action == "int":
        if text.isdigit() and 1 <= int(text) <= 1440:
            conn.execute("INSERT INTO settings (user_id, interval) VALUES (?,?) ON CONFLICT DO UPDATE SET interval=?", (uid, int(text), int(text)))
            await update.message.reply_text(f"⏱ الفاصل {text} دقيقة")
        else: await update.message.reply_text("⚠️ رقم بين 1-1440")
    elif action == "post":
        if update.message.photo:
            typ, fid, cap = "photo", update.message.photo[-1].file_id, update.message.caption
        elif update.message.video:
            typ, fid, cap = "video", update.message.video.file_id, update.message.caption
        else:
            typ, fid, cap = "text", None, text
        conn.execute("INSERT INTO posts (user_id, type, file_id, cap, txt, channel_id) VALUES (?,?,?,?,?,?)", (uid, typ, fid, cap, text if typ=="text" else None, None))
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
            users = conn.execute("SELECT user_id, interval FROM settings WHERE (? - last_time) >= (interval*60) AND paused=0", (now,)).fetchall()
            for uid, interval in users:
                channels = [r[0] for r in conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()]
                if not channels: continue
                post = conn.execute("SELECT type, file_id, cap, txt FROM posts WHERE user_id=? ORDER BY RANDOM() LIMIT 1", (uid,)).fetchone()
                if not post: continue
                typ, fid, cap, txt = post
                conn.execute("UPDATE settings SET last_time=? WHERE user_id=?", (now, uid))
                conn.commit()
                for ch in channels:
                    try:
                        if typ == "text": await app.bot.send_message(ch, text=txt)
                        elif typ == "photo": await app.bot.send_photo(ch, photo=fid, caption=cap)
                        elif typ == "video": await app.bot.send_video(ch, video=fid, caption=cap)
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
