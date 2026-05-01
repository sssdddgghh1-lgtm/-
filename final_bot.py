import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import Forbidden, BadRequest, TelegramError

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
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

# --- وظائف المساعدة ---
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

# --- الواجهة الرئيسية ---
async def menu(update, context, is_cb=False):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    # تنبيه الأدمن بالمستخدم الجديد
    with sqlite3.connect(DB_NAME) as conn:
        is_exist = conn.execute("SELECT 1 FROM settings WHERE user_id=?", (uid,)).fetchone()
        if not is_exist:
            conn.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
            try: await context.bot.send_message(ADMIN_ID, f"🆕 **مستخدم جديد انضم للبوت!**\n👤 الاسم: {update.effective_user.first_name}\n🆔 الآيدي: `{uid}`")
            except: pass

    if await is_banned(uid):
        msg = "❌ نعتذر، لقد تم حظرك من استخدام البوت."
        if is_cb: await update.callback_query.edit_message_text(msg)
        else: await update.message.reply_text(msg)
        return

    if not await check_sub(uid, context):
        with sqlite3.connect(DB_NAME) as conn:
            sub_ch = conn.execute("SELECT channel_id FROM force_sub WHERE id=1").fetchone()[0]
        kb = [[InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{sub_ch.replace('@','')}")]]
        t = f"⚠️ **يجب الاشتراك في القناة أولاً لتتمكن من استخدام البوت:**\n{sub_ch}"
        if is_cb: await update.callback_query.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb))
        else: await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = [
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="ch"), InlineKeyboardButton("📝 إضافة منشور", callback_data="post")],
        [InlineKeyboardButton("🗑 حذف منشور", callback_data="del_list"), InlineKeyboardButton("⏱ ضبط الفاصل", callback_data="int")],
        [InlineKeyboardButton("📊 الحالة", callback_data="stat")]
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("⚙️ إعدادات الأدمن", callback_data="admin_menu")])
    
    t = "💎 **مرحباً بك في بوت النشر التلقائي المطور**\nاستخدم الأزرار أدناه للتحكم."
    if is_cb: await update.callback_query.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))

# --- معالج الأزرار ---
async def callback_handler(update, context):
    if not update.effective_user: return
    q = update.callback_query
    uid = update.effective_user.id
    if await is_banned(uid): return
    await q.answer()
    
    if q.data == "menu": await menu(update, context, True)
    elif q.data == "admin_menu" and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("🚫 حظر", callback_data="ban_user"), InlineKeyboardButton("✅ فك حظر", callback_data="unban_user")],
            [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="view_stats"), InlineKeyboardButton("👥 القنوات", callback_data="view_users_chs")],
            [InlineKeyboardButton("📢 قناة الاشتراك", callback_data="set_sub"), InlineKeyboardButton("📣 إذاعة", callback_data="bc")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu")]
        ]
        await q.edit_message_text("⚙️ **لوحة التحكم الإدارية:**", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == "view_stats" and uid == ADMIN_ID:
        today = time.strftime("%Y-%m-%d")
        with sqlite3.connect(DB_NAME) as conn:
            total_pub = conn.execute("SELECT SUM(count) FROM stats").fetchone()[0] or 0
            today_pub = conn.execute("SELECT count FROM stats WHERE date=?", (today,)).fetchone()
            today_pub = today_pub[0] if today_pub else 0
            users_count = conn.execute("SELECT COUNT(DISTINCT user_id) FROM settings").fetchone()[0]
            posts_count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        msg = f"📈 **إحصائيات البوت المباشرة:**\n\n"
        msg += f"✅ منشورات اليوم: `{today_pub}`\n"
        msg += f"🌍 إجمالي النشر: `{total_pub}`\n"
        msg += f"👤 عدد المستخدمين: `{users_count}`\n"
        msg += f"📝 إجمالي المنشورات: `{posts_count}`"
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="admin_menu")]]))
    elif q.data == "ban_user" and uid == ADMIN_ID:
        context.user_data['action'] = "ban"; await q.edit_message_text("🚫 أرسل ID المستخدم لحظره:")
    elif q.data == "unban_user" and uid == ADMIN_ID:
        context.user_data['action'] = "unban"; await q.edit_message_text("✅ أرسل ID لفك الحظر:")
    elif q.data == "view_users_chs" and uid == ADMIN_ID:
        with sqlite3.connect(DB_NAME) as conn:
            data = conn.execute("SELECT user_id, chat_id FROM channels").fetchall()
        msg = "👥 **قنوات المستخدمين المضافة:**\n\n" + ("\n".join([f"👤 `{r[0]}` 📢 {r[1]}" for r in data]) if data else "❌ لا يوجد")
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="admin_menu")]]))
    elif q.data == "set_sub" and uid == ADMIN_ID:
        context.user_data['action'] = "change_sub"; await q.edit_message_text("⚙️ أرسل معرف القناة الجديد (مثلاً @zzimmiie):")
    elif q.data == "bc" and uid == ADMIN_ID:
        context.user_data['action'] = "bc"; await q.edit_message_text("📣 أرسل رسالة الإذاعة لجميع المستخدمين:")
    elif q.data == "del_list":
        with sqlite3.connect(DB_NAME) as conn:
            posts = conn.execute("SELECT id, chat_id, SUBSTR(cap_html, 1, 15) FROM posts WHERE user_id=?", (uid,)).fetchall()
        if not posts: return await q.edit_message_text("❌ لا يوجد لديك منشورات حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu")]]))
        kb = [[InlineKeyboardButton(f"❌ حذف: {p[2]}..", callback_data=f"remove_{p[0]}")] for p in posts]
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu")])
        await q.edit_message_text("🗑 اختر المنشور الذي ترغب بحذفه:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("remove_"):
        pid = q.data.replace("remove_", "")
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM posts WHERE id=? AND user_id=?", (pid, uid)); conn.commit()
        await q.edit_message_text("✅ تم حذف المنشور بنجاح!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="del_list")]]))
    elif q.data == "ch":
        context.user_data['action'] = "ch"; await q.edit_message_text("📝 أرسل معرف قناتك (يجب أن يكون البوت مشرفاً فيها):")
    elif q.data == "post":
        with sqlite3.connect(DB_NAME) as conn:
            chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        if not chs: return await q.edit_message_text("❌ لم تقم بإضافة أي قناة بعد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
        kb = [[InlineKeyboardButton(f"🎯 {c[0]}", callback_data=f"target_{c[0]}")] for c in chs]
        await q.edit_message_text("🎯 اختر القناة التي تريد إضافة المنشور إليها:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("target_"):
        context.user_data['target'] = q.data.replace("target_", ""); context.user_data['action'] = "up"
        await q.edit_message_text(f"✅ أرسل نص المنشور الآن لقناة {context.user_data['target']}:")
    elif q.data == "stat":
        with sqlite3.connect(DB_NAME) as conn:
            pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
            it = conn.execute("SELECT interval FROM settings WHERE user_id=?", (uid,)).fetchone()
            interval = it[0] if it else 60
        await q.edit_message_text(f"📊 **حالة حسابك:**\n- عدد منشوراتك: `{pc}`\n- الفاصل الحالي: `{interval}` دقيقة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu")]]))
    elif q.data == "int":
        context.user_data['action'] = "int"; await q.edit_message_text("⏱ أرسل الفاصل الزمني بالدقائق (أقل مدة 12 دقيقة):")

# --- معالج المدخلات النصية ---
async def handle_inputs(update, context):
    if not update.effective_user: return
    uid = update.effective_user.id
    if await is_banned(uid): return
    action = context.user_data.get('action')
    if not action: return
    
    with sqlite3.connect(DB_NAME) as conn:
        try:
            if action == "ban" and uid == ADMIN_ID:
                conn.execute("INSERT OR IGNORE INTO banned VALUES (?)", (int(update.message.text),))
                await update.message.reply_text("🚫 تم حظر المستخدم.")
            elif action == "unban" and uid == ADMIN_ID:
                conn.execute("DELETE FROM banned WHERE user_id=?", (int(update.message.text),))
                await update.message.reply_text("✅ تم فك الحظر.")
            elif action == "ch":
                conn.execute("INSERT OR IGNORE INTO channels VALUES (?,?)", (uid, update.message.text))
                await update.message.reply_text("✅ تمت إضافة القناة بنجاح.")
            elif action == "up":
                conn.execute("INSERT INTO posts (user_id, chat_id, cap_html) VALUES (?,?,?)", (uid, context.user_data['target'], update.message.text_html))
                await update.message.reply_text("✅ تم حفظ المنشور بنجاح.")
            elif action == "int" and update.message.text.isdigit():
                val = int(update.message.text)
                if val < 12:
                    await update.message.reply_text("⚠️ تنبيه: أقل مدة مسموحة هي 12 دقيقة لحماية القنوات من السبام.")
                    return
                conn.execute("UPDATE settings SET interval=? WHERE user_id=?", (val, uid))
                await update.message.reply_text(f"✅ تم ضبط الفاصل إلى {val} دقيقة.")
            elif action == "change_sub" and uid == ADMIN_ID:
                conn.execute("UPDATE force_sub SET channel_id=? WHERE id=1", (update.message.text,))
                await update.message.reply_text("✅ تم تحديث قناة الاشتراك الإجباري.")
            elif action == "bc" and uid == ADMIN_ID:
                users = conn.execute("SELECT user_id FROM settings").fetchall()
                for u in users:
                    try: await context.bot.send_message(u[0], f"📣 **إعلان من الإدارة:**\n\n{update.message.text}")
                    except: pass
                await update.message.reply_text("✅ تم إرسال الإذاعة للجميع.")
        except Exception: pass
    
    context.user_data['action'] = None; await menu(update, context)

# --- محرك النشر التلقائي ---
async def publisher(app):
    while True:
        await asyncio.sleep(60)
        now = int(time.time())
        today = time.strftime("%Y-%m-%d")
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute("SELECT * FROM settings WHERE (? - last_time) >= (interval*60)", (now,)).fetchall()
            for u in users:
                if await is_banned(u['user_id']): continue
                chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (u['user_id'],)).fetchall()
                for c in chs:
                    p = conn.execute("SELECT * FROM posts WHERE user_id=? AND chat_id=? ORDER BY last_used ASC LIMIT 1", (u['user_id'], c['chat_id'])).fetchone()
                    if p:
                        try:
                            await app.bot.send_message(c['chat_id'], p['cap_html'], parse_mode="HTML")
                            conn.execute("UPDATE posts SET last_used=? WHERE id=?", (now, p['id']))
                            conn.execute("INSERT OR IGNORE INTO stats (date, count) VALUES (?, 0)", (today,))
                            conn.execute("UPDATE stats SET count = count + 1 WHERE date=?", (today,))
                        except Forbidden:
                            try: await app.bot.send_message(u['user_id'], f"⚠️ **تنبيه:** البوت فقد صلاحية النشر في {c['chat_id']}. يرجى إعادته آدمن.")
                            except: pass
                        except BadRequest: pass
                        except TelegramError: pass
                conn.execute("UPDATE settings SET last_time=? WHERE user_id=?", (now, u['user_id']))
                conn.commit()

def run():
    if not BOT_TOKEN: return print("❌ خطأ: التوكن غير موجود!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", menu))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inputs))
    asyncio.get_event_loop().create_task(publisher(app))
    print("🚀 تم تشغيل البوت بنجاح..")
    app.run_polling()

if __name__ == "__main__":
    run()
