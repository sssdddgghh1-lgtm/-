import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import Forbidden, BadRequest, TelegramError

# --- الإعدادات الأساسية ---
# تم سحب التوكن تلقائياً من ترمكس
BOT_TOKEN = "8295665183:AAHERIriMQMc_x8Mz-_x5I8Ef87JB8Wnvyo" 
ADMIN_ID = 7983340250 
DB_NAME = "auto_publisher.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS channels (user_id INT, chat_id TEXT, PRIMARY KEY(user_id, chat_id))')
        conn.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, chat_id TEXT, cap_html TEXT, last_used INT DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS settings (user_id INT PRIMARY KEY, interval INT DEFAULT 60, last_time INT DEFAULT 0, paused INT DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS force_sub (id INT PRIMARY KEY, channel_id TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS banned (user_id INT PRIMARY KEY)')
        conn.execute('CREATE TABLE IF NOT EXISTS stats (date TEXT PRIMARY KEY, count INT DEFAULT 0)')
        conn.execute('INSERT OR IGNORE INTO force_sub VALUES (1, "@zzimmiie")')
init_db()

async def is_banned(uid):
    if not uid: return False
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,)).fetchone() is not None

async def check_sub(uid, context):
    if uid == ADMIN_ID: return True
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT channel_id FROM force_sub WHERE id=1").fetchone()
        sub_ch = res[0] if res else "@zzimmiie"
    try:
        m = await context.bot.get_chat_member(sub_ch, uid)
        return m.status in ['member', 'administrator', 'creator']
    except: return False

async def menu(update, context, is_cb=False):
    if not update.effective_user: return
    uid = update.effective_user.id
    with sqlite3.connect(DB_NAME) as conn:
        is_exist = conn.execute("SELECT 1 FROM settings WHERE user_id=?", (uid,)).fetchone()
        if not is_exist:
            conn.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
            try: await context.bot.send_message(ADMIN_ID, f"🆕 **مستخدم جديد!**\n👤 {update.effective_user.first_name}\n🆔 `{uid}`", parse_mode="Markdown")
            except: pass
    if await is_banned(uid):
        msg = "❌ محظور."
        if is_cb: await update.callback_query.edit_message_text(msg)
        else: await update.message.reply_text(msg)
        return
    if not await check_sub(uid, context):
        with sqlite3.connect(DB_NAME) as conn:
            sub_ch = conn.execute("SELECT channel_id FROM force_sub WHERE id=1").fetchone()[0]
        kb = [[InlineKeyboardButton("📢 اشترك", url=f"https://t.me/{sub_ch.replace('@','')}")]]
        t = f"⚠️ اشترك أولاً: {sub_ch}"
        if is_cb: await update.callback_query.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb))
        else: await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton("➕ إضافة قناة", callback_data="ch"), InlineKeyboardButton("📝 إضافة منشور", callback_data="post")],
          [InlineKeyboardButton("🗑 حذف منشور", callback_data="del_list"), InlineKeyboardButton("⏱ ضبط الفاصل", callback_data="int")],
          [InlineKeyboardButton("📊 الحالة", callback_data="stat")]]
    if uid == ADMIN_ID: kb.append([InlineKeyboardButton("⚙️ إعدادات الأدمن", callback_data="admin_menu")])
    t = "💎 **بوت النشر التلقائي المطور**"
    if is_cb: await update.callback_query.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update, context):
    q = update.callback_query
    uid = update.effective_user.id
    await q.answer()
    if q.data == "menu": await menu(update, context, True)
    elif q.data == "ch":
        context.user_data['action'] = "ch"; await q.edit_message_text("📝 أرسل معرف القناة:")
    elif q.data == "post":
        with sqlite3.connect(DB_NAME) as conn:
            chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        if not chs: return await q.edit_message_text("❌ أضف قناة أولاً.")
        kb = [[InlineKeyboardButton(f"🎯 {c[0]}", callback_data=f"target_{c[0]}")] for c in chs]
        await q.edit_message_text("🎯 اختر القناة:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("target_"):
        context.user_data['target'] = q.data.replace("target_", ""); context.user_data['action'] = "up"
        await q.edit_message_text(f"✅ أرسل نص المنشور لـ {context.user_data['target']}:")
    elif q.data == "stat":
        with sqlite3.connect(DB_NAME) as conn:
            pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
            it = conn.execute("SELECT interval FROM settings WHERE user_id=?", (uid,)).fetchone()[0]
        await q.edit_message_text(f"📊 منشوراتك: {pc}\n⏱ الفاصل: {it} دقيقة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif q.data == "int":
        context.user_data['action'] = "int"; await q.edit_message_text("⏱ أرسل الفاصل بالدقائق (مثال: 30):")

async def handle_inputs(update, context):
    uid = update.effective_user.id
    action = context.user_data.get('action')
    if not action: return
    with sqlite3.connect(DB_NAME) as conn:
        if action == "ch":
            conn.execute("INSERT OR IGNORE INTO channels VALUES (?,?)", (uid, update.message.text))
            await update.message.reply_text("✅ تمت الإضافة.")
        elif action == "up":
            conn.execute("INSERT INTO posts (user_id, chat_id, cap_html) VALUES (?,?,?)", (uid, context.user_data['target'], update.message.text_html))
            await update.message.reply_text("✅ تم الحفظ.")
        elif action == "int" and update.message.text.isdigit():
            conn.execute("UPDATE settings SET interval=? WHERE user_id=?", (int(update.message.text), uid))
            await update.message.reply_text("✅ تم الضبط.")
    context.user_data['action'] = None; await menu(update, context)

async def publisher(app):
    while True:
        await asyncio.sleep(60)
        now = int(time.time())
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute("SELECT * FROM settings WHERE (? - last_time) >= (interval*60)", (now,)).fetchall()
            for u in users:
                chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (u['user_id'],)).fetchall()
                for c in chs:
                    p = conn.execute("SELECT * FROM posts WHERE user_id=? AND chat_id=? ORDER BY last_used ASC LIMIT 1", (u['user_id'], c['chat_id'])).fetchone()
                    if p:
                        try:
                            await app.bot.send_message(c['chat_id'], p['cap_html'], parse_mode="HTML")
                            conn.execute("UPDATE posts SET last_used=? WHERE id=?", (now, p['id']))
                        except: pass
                conn.execute("UPDATE settings SET last_time=? WHERE user_id=?", (now, u['user_id']))
                conn.commit()

def run():
    if not BOT_TOKEN or BOT_TOKEN == "": return print("❌ خطأ: التوكن لم يسحب من ترمكس!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", menu))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inputs))
    asyncio.get_event_loop().create_task(publisher(app))
    print("🚀 تم تشغيل البوت بنجاح..")
    app.run_polling()

if __name__ == "__main__":
    run()
