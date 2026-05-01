import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

DB_NAME = "final_bot.db"
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
    c.execute('CREATE TABLE IF NOT EXISTS settings (user_id INT PRIMARY KEY, interval INT, last_time INT, paused INT)')
    conn.commit()
    conn.close()
init_db()

POST, INTERVAL, DELETE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ قناة", callback_data="ch")],
        [InlineKeyboardButton("➕ منشور", callback_data="post")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list")],
        [InlineKeyboardButton("📊 حالة", callback_data="stat")],
        [InlineKeyboardButton("⏱ فاصل", callback_data="int")],
        [InlineKeyboardButton("⏸ ايقاف", callback_data="pause")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="del")]
    ])
    await update.message.reply_text("🔧 بوت النشر الذكي", reply_markup=kb)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    conn = get_db()

    if data == "ch":
        await query.edit_message_text("ارسل معرف القناة (@username):")
        return
    elif data == "list":
        chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        txt = "\n".join([f"• {r[0]}" for r in chs]) if chs else "لا توجد قنوات"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]))
    elif data == "stat":
        pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        cc = conn.execute("SELECT COUNT(*) FROM channels WHERE user_id=?", (uid,)).fetchone()[0]
        await query.edit_message_text(f"📦 منشورات: {pc}\n📢 قنوات: {cc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]))
    elif data == "pause":
        conn.execute("INSERT INTO settings (user_id, paused) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET paused = 1 - paused", (uid,))
        conn.commit()
        await query.edit_message_text("✅ تم تغيير حالة التشغيل")
    elif data == "back":
        await start(update, context)
    elif data == "post":
        await query.edit_message_text("ارسل المنشور (نص، صورة، فيديو):")
        return POST
    elif data == "int":
        await query.edit_message_text("ارسل عدد الدقائق (1-1440):")
        return INTERVAL
    elif data == "del":
        await query.edit_message_text("ارسل معرف القناة للحذف:")
        return DELETE
    conn.close()
    return ConversationHandler.END

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    action = context.user_data.get('action')
    conn = get_db()

    if action == 'add_ch':
        conn.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)", (uid, text))
        await update.message.reply_text(f"✅ تم اضافة {text}")
    elif action == 'del_ch':
        conn.execute("DELETE FROM channels WHERE user_id=? AND chat_id=?", (uid, text))
        await update.message.reply_text("✅ تم الحذف")
    elif action == 'set_int':
        if text.isdigit() and 1 <= int(text) <= 1440:
            conn.execute("INSERT INTO settings (user_id, interval) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET interval=?", (uid, int(text), int(text)))
            await update.message.reply_text(f"⏱ تم ضبط الفاصل {text} دقيقة")
        else:
            await update.message.reply_text("⚠️ ارسل رقم بين 1 و 1440")
    elif action == 'add_post':
        if update.message.photo:
            t, fid, cap = "photo", update.message.photo[-1].file_id, update.message.caption
        elif update.message.video:
            t, fid, cap = "video", update.message.video.file_id, update.message.caption
        else:
            t, fid, cap = "text", None, text
        conn.execute("INSERT INTO posts (user_id, type, fid, cap, txt) VALUES (?, ?, ?, ?, ?)", (uid, t, fid, cap, text if t=="text" else None))
        await update.message.reply_text("✅ تم حفظ المنشور")

    conn.commit()
    conn.close()
    await start(update, context)
    return ConversationHandler.END

async def auto_post(app):
    while True:
        await asyncio.sleep(30)  # افحص كل 30 ثانية

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.ALL, handle_text))
    asyncio.create_task(auto_post(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
