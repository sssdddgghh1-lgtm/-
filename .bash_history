            await asyncio.sleep(e.retry_after)
        except Exception as e:
            return None
    return None

# ============= معالج الأزرار الرئيسي =============
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id
    
    # الأزرار السريعة (تستجيب مباشرة)
    if data == "list_ch":
        conn = get_db()
        c = conn.cursor()
        chs = c.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        conn.close()
        txt = "\n".join([f"• {r[0]}" for r in chs]) if chs else "📭 لا توجد قنوات"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))
        return
    
    if data == "stat":
        conn = get_db()
        c = conn.cursor()
        pc = c.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        cc = c.execute("SELECT COUNT(*) FROM channels WHERE user_id=?", (uid,)).fetchone()[0]
        conn.close()
        await query.edit_message_text(f"📊 منشورات: {pc}\n📢 قنوات: {cc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))
        return
    
    if data == "toggle_pause":
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO user_settings (user_id, is_paused) VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET is_paused = 1 - is_paused", (uid,))
        conn.commit()
        conn.close()
        await show_panel(update)
        return
    
    if data == "main_menu":
        await show_panel(update)
        return
    
    # الأزرار اللي تحتاج إدخال (تدخل ConversationHandler)
    if data in ["add_ch", "add_p", "set_i", "del_ch"]:
        prompts = {
            "add_ch": "📢 أرسل معرف القناة (@username):",
            "add_p": "➕ أرسل المنشور (نص، صورة، فيديو):",
            "set_i": "⏱ أرسل عدد الدقائق (1-1440):",
            "del_ch": "🗑 أرسل معرف القناة للحذف:"
        }
        await query.edit_message_text(prompts[data])
        context.user_data['action'] = data
        return ConversationHandler.END
    
    # معالجة اختيار القناة للمنشور
    if data.startswith("ch_"):
        selected = "all" if data == "ch_all" else data[3:]
        context.user_data['selected_channel'] = selected
        await query.edit_message_text("✅ تم اختيار القناة، الآن أرسل المنشور:")
        return

    if data == "cancel_post":
        context.user_data.pop('temp_post', None)
        context.user_data.pop('selected_channel', None)
        await query.edit_message_text("❌ تم الإلغاء")
        await show_panel(update)
        return

# ============= معالج الرسائل =============
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    action = context.user_data.get('action')
    conn = get_db()
    c = conn.cursor()
    
    if action == "add_ch":
        c.execute("INSERT OR IGNORE INTO channels (user_id, chat_id) VALUES (?, ?)", (uid, text))
        await update.message.reply_text(f"✅ تم إضافة القناة {text}")
        context.user_data['action'] = None
        
    elif action == "del_ch":
        c.execute("DELETE FROM channels WHERE user_id=? AND chat_id=?", (uid, text))
        await update.message.reply_text("✅ تم حذف القناة" if c.rowcount else "⚠️ غير موجودة")
        context.user_data['action'] = None
        
    elif action == "set_i":
        if text.isdigit() and 1 <= int(text) <= 1440:
            c.execute("INSERT INTO user_settings (user_id, interval) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET interval=?", (uid, int(text), int(text)))
            await update.message.reply_text(f"⏱ تم ضبط الفاصل {text} دقيقة")
        else:
            await update.message.reply_text("⚠️ أرسل رقم بين 1 و 1440")
        context.user_data['action'] = None
        
    elif action == "add_p":
        # حفظ نوع المنشور
        if update.message.photo:
            typ, fid, cap = "photo", update.message.photo[-1].file_id, update.message.caption
        elif update.message.video:
            typ, fid, cap = "video", update.message.video.file_id, update.message.caption
        elif update.message.document:
            typ, fid, cap = "document", update.message.document.file_id, update.message.caption
        elif update.message.audio:
            typ, fid, cap = "audio", update.message.audio.file_id, update.message.caption
        elif update.message.voice:
            typ, fid, cap = "voice", update.message.voice.file_id, update.message.caption
        elif update.message.sticker:
            typ, fid = "sticker", update.message.sticker.file_id
            cap = None
        else:
            typ, fid, cap = "text", None, text
        
        # طلب اختيار القناة
        channels = c.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        if not channels:
            await update.message.reply_text("⚠️ لا توجد قنوات. أضف قناة أولاً.")
            context.user_data['action'] = None
        else:
            context.user_data['temp_post'] = (typ, fid, cap, text if typ=="text" else None)
            kb_buttons = []
            for ch in channels:
                kb_buttons.append([InlineKeyboardButton(f"📢 {ch[0]}", callback_data=f"ch_{ch[0]}")])
            kb_buttons.append([InlineKeyboardButton("📡 جميع القنوات", callback_data="ch_all")])
            kb_buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_post")])
            await update.message.reply_text("لأي قناة؟", reply_markup=InlineKeyboardMarkup(kb_buttons))
            context.user_data['action'] = 'waiting_channel'
            
    elif action == 'waiting_channel':
        selected = context.user_data.get('selected_channel')
        temp_post = context.user_data.get('temp_post')
        if temp_post and selected:
            typ, fid, cap, txt = temp_post
            channel_id = None if selected == "all" else selected
            c.execute("INSERT INTO posts (user_id, type, file_id, caption, text, channel_id) VALUES (?,?,?,?,?,?)",
                     (uid, typ, fid, cap, txt, channel_id))
            await update.message.reply_text("✅ تم حفظ المنشور")
            context.user_data.pop('temp_post', None)
            context.user_data.pop('selected_channel', None)
            context.user_data['action'] = None
    
    conn.commit()
    conn.close()
    await show_panel(update)

async def auto_poster(app: Application):
    while True:
        try:
            now = int(time.time())
            conn = get_db()
            c = conn.cursor()
            users = c.execute("SELECT user_id, interval FROM user_settings WHERE (? - last_post_time) >= (interval*60) AND is_paused=0", (now,)).fetchall()
            for uid, interval in users:
                channels = [r[0] for r in c.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()]
                if not channels: continue
                for ch in channels:
                    post = c.execute("SELECT type, file_id, caption, text FROM posts WHERE user_id=? AND (channel_id=? OR channel_id IS NULL) ORDER BY RANDOM() LIMIT 1", (uid, ch)).fetchone()
                    if not post: continue
                    typ, fid, cap, txt = post
                    try:
                        if typ == "text": await send_with_retry(app.bot.send_message, chat_id=ch, text=txt)
                        elif typ == "photo": await send_with_retry(app.bot.send_photo, chat_id=ch, photo=fid, caption=cap)
                        elif typ == "video": await send_with_retry(app.bot.send_video, chat_id=ch, video=fid, caption=cap)
                        elif typ == "document": await send_with_retry(app.bot.send_document, chat_id=ch, document=fid, caption=cap)
                        elif typ == "audio": await send_with_retry(app.bot.send_audio, chat_id=ch, audio=fid, caption=cap)
                        elif typ == "voice": await send_with_retry(app.bot.send_voice, chat_id=ch, voice=fid, caption=cap)
                        elif typ == "sticker": await send_with_retry(app.bot.send_sticker, chat_id=ch, sticker=fid)
                    except: pass
                c.execute("UPDATE user_settings SET last_post_time=? WHERE user_id=?", (now, uid))
                conn.commit()
            conn.close()
        except: pass
        await asyncio.sleep(30)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_panel(update)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    asyncio.create_task(auto_poster(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
EOF

python bot2_multi_fixed.py
sqlite3 bot.db "SELECT user_id, last_post_time, datetime(last_post_time, 'unixepoch') FROM user_settings;"
python bot2_multi_fixed.py
# 1. حذف النسخة القديمة
rm -f final_bot.py
# 2. إنشاء النسخة المخصصة (تعتمد على توكن النظام وتدعم استقلالية القنوات)
cat > final_bot.py << 'EOF'
import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# سحب التوكن المحفوظ في ترمكس تلقائياً
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_NAME = "final_bot.db"

logging.basicConfig(level=logging.INFO)

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS channels (user_id INT, chat_id TEXT, PRIMARY KEY(user_id, chat_id))')
        # إضافة عمود chat_id في جدول المنشورات لربط كل منشور بقناة
        conn.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, chat_id TEXT, type TEXT, file_id TEXT, cap_html TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS settings (user_id INT PRIMARY KEY, interval INT DEFAULT 60, last_time INT DEFAULT 0, paused INT DEFAULT 0)')

init_db()

async def menu(update, context, is_callback=False):
    kb = [[InlineKeyboardButton("📢 القنوات", callback_data="ch"), InlineKeyboardButton("📝 إضافة منشور", callback_data="post")],
          [InlineKeyboardButton("⏱ الفاصل", callback_data="int"), InlineKeyboardButton("📊 الحالة", callback_data="stat")],
          [InlineKeyboardButton("⏯ إيقاف/تشغيل", callback_data="pause"), InlineKeyboardButton("🗑 تفريغ الكل", callback_data="clear_posts")]]
    txt = "💎 **بوت النشر المخصص المستقل**\n\nقم بربط كل منشور بقناة معينة بسهولة."
    if is_callback: await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else: await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def callback_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    
    if q.data == "menu": await menu(update, context, True)
    elif q.data == "post":
        with sqlite3.connect(DB_NAME) as conn:
            ch_list = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        if not ch_list:
            await q.edit_message_text("❌ أضف قناة أولاً!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
            return
        kb = [[InlineKeyboardButton(f"🎯 تخصيص لـ {c[0]}", callback_data=f"set_target_{c[0]}")] for c in ch_list]
        await q.edit_message_text("اختر القناة التي تريد رفع المنشورات إليها:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("set_target_"):
        context.user_data['target_ch'] = q.data.replace("set_target_", "")
        context.user_data['action'] = "uploading"
        await q.edit_message_text(f"✅ سيتم الحفظ لـ: {context.user_data['target_ch']}\nأرسل المنشورات الآن:")
    elif q.data == "stat":
        with sqlite3.connect(DB_NAME) as conn:
            pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        await q.edit_message_text(f"📊 إجمالي المنشورات: {pc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif q.data == "clear_posts":
        with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM posts WHERE user_id=?", (uid,))
        await q.edit_message_text("🗑 تم الحذف.")
    else:
        context.user_data['action'] = q.data
        await q.edit_message_text("📝 أرسل البيانات:")

async def handle_inputs(update, context):
    action = context.user_data.get('action')
    uid = update.effective_user.id
    if not action: return

    with sqlite3.connect(DB_NAME) as conn:
        if action == "ch":
            conn.execute("INSERT OR IGNORE INTO channels VALUES (?,?)", (uid, update.message.text))
            await update.message.reply_text(f"✅ تمت إضافة {update.message.text}")
        elif action == "uploading":
            target = context.user_data.get('target_ch')
            cap = update.message.caption_html if update.message.caption else update.message.text_html
            m_type = "photo" if update.message.photo else "video" if update.message.video else "text"
            f_id = update.message.photo[-1].file_id if update.message.photo else update.message.video.file_id if update.message.video else None
            conn.execute("INSERT INTO posts (user_id, chat_id, type, file_id, cap_html) VALUES (?,?,?,?,?)", (uid, target, m_type, f_id, cap))
            await update.message.reply_text(f"✅ حفظ لـ {target}. أرسل المزيد أو /start")
            return
        elif action == "int":
            if update.message.text.isdigit():
                conn.execute("INSERT INTO settings (user_id, interval) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET interval=?", (uid, int(update.message.text), int(update.message.text)))
                await update.message.reply_text("✅ تم تحديث الفاصل.")

    context.user_data['action'] = None
    await menu(update, context)

async def auto_publisher(app):
    while True:
        await asyncio.sleep(30)
        now = int(time.time())
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute("SELECT * FROM settings WHERE (? - last_time) >= (interval*60) AND paused=0", (now,)).fetchall()
            for u in users:
                channels = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (u['user_id'],)).fetchall()
                for c in channels:
                    # جلب منشور عشوائي مخصص لهذه القناة فقط
                    post = conn.execute("SELECT * FROM posts WHERE user_id=? AND chat_id=? ORDER BY RANDOM() LIMIT 1", (u['user_id'], c['chat_id'])).fetchone()
                    if post:
                        try:
                            if post['type'] == "photo": await app.bot.send_photo(c['chat_id'], photo=post['file_id'], caption=post['cap_html'], parse_mode="HTML")
                            elif post['type'] == "video": await app.bot.send_video(c['chat_id'], video=post['file_id'], caption=post['cap_html'], parse_mode="HTML")
                            else: await app.bot.send_message(c['chat_id'], text=post['cap_html'], parse_mode="HTML")
                        except: pass
                conn.execute("UPDATE settings SET last_time=? WHERE user_id=?", (now, u['user_id']))
                conn.commit()

def run():
    if not BOT_TOKEN:
        print("❌ خطأ: لم يتم العثور على BOT_TOKEN في نظام ترمكس!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", menu))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_inputs))
    asyncio.get_event_loop().create_task(auto_publisher(app))
    print("🚀 البوت يعمل بالتوكن المحفوظ في نظامك...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    run()
EOF

# 3. التشغيل المباشر (بدون أي توكن في الأوامر)
python final_bot.py
pkill -f python ; cat > final_bot.py << 'EOF'
import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandlepkill -f python ; cat > final_bot.py << 'EOF'
import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- الإعدادات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7983340250 
DB_NAME = "auto_publisher.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS channels (user_id INT, chat_id TEXT, PRIMARY KEY(user_id, chat_id))')
        conn.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, chat_id TEXT, cap_html TEXT, last_used INT DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS settings (user_id INT PRIMARY KEY, interval INT DEFAULT 60, last_time INT DEFAULT 0, paused INT DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS force_sub (id INT PRIMARY KEY, channel_id TEXT)')
        conn.execute('INSERT OR IGNORE INTO force_sub VALUES (1, "@zzimmiie")')
init_db()

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
    uid = update.effective_user.id
    if not await check_sub(uid, context):
        with sqlite3.connect(DB_NAME) as conn:
            sub_ch = conn.execute("SELECT channel_id FROM force_sub WHERE id=1").fetchone()[0]
        kb = [[InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{sub_ch.replace('@','')}")]]
        t = f"⚠️ يجب الاشتراك في القناة أولاً:\n{sub_ch}"
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
    
    t = "💎 **لوحة تحكم النشر التلقائي**"
    if is_cb: await update.callback_query.edit_message_text(t, reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update, context):
    q = update.callback_query
    uid = update.effective_user.id
    await q.answer()
    
    if q.data == "menu": await menu(update, context, True)
    
    # --- قسم الأدمن ---
    elif q.data == "admin_menu" and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("📢 تغيير الاشتراك الإجباري", callback_data="set_sub")],
            [InlineKeyboardButton("📣 إرسال إذاعة للكل", callback_data="bc")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="menu")]
        ]
        await q.edit_message_text("⚙️ **مرحباً بك في لوحة تحكم الإدارة:**", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data == "set_sub" and uid == ADMIN_ID:
        context.user_data['action'] = "change_sub"
        await q.edit_message_text("⚙️ أرسل معرف القناة الجديد (مثال: @zzimmiie):")

    elif q.data == "bc" and uid == ADMIN_ID:
        context.user_data['action'] = "bc"
        await q.edit_message_text("📣 أرسل الآن الرسالة التي تريد إرسالها لجميع مستخدمي البوت:")
    
    # --- قسم الحذف ---
    elif q.data == "del_list":
        with sqlite3.connect(DB_NAME) as conn:
            posts = conn.execute("SELECT id, chat_id, SUBSTR(cap_html, 1, 15) FROM posts WHERE user_id=?", (uid,)).fetchall()
        if not posts:
            return await q.edit_message_text("❌ لا يوجد منشورات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu")]]))
        kb = [[InlineKeyboardButton(f"❌ حذف: {p[2]}..", callback_data=f"remove_{p[0]}")] for p in posts]
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu")])
        await q.edit_message_text("🗑 اختر المنشور لحذفه:", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data.startswith("remove_"):
        pid = q.data.replace("remove_", "")
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM posts WHERE id=? AND user_id=?", (pid, uid))
            conn.commit()
        await q.edit_message_text("✅ تم الحذف!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="del_list")]]))

    # --- الأوامر العادية ---
    elif q.data == "ch":
        context.user_data['action'] = "ch"
        await q.edit_message_text("📝 أرسل معرف قناتك:")
    elif q.data == "post":
        with sqlite3.connect(DB_NAME) as conn:
            chs = conn.execute("SELECT chat_id FROM channels WHERE user_id=?", (uid,)).fetchall()
        if not chs: return await q.edit_message_text("❌ أضف قناة أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
        kb = [[InlineKeyboardButton(f"🎯 {c[0]}", callback_data=f"target_{c[0]}")] for c in chs]
        await q.edit_message_text("🎯 اختر القناة الهدف:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("target_"):
        context.user_data['target'] = q.data.replace("target_", "")
        context.user_data['action'] = "up"
        await q.edit_message_text(f"✅ أرسل نص المنشور لـ {context.user_data['target']}:")
    elif q.data == "stat":
        with sqlite3.connect(DB_NAME) as conn:
            pc = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        await q.edit_message_text(f"📊 منشوراتك: {pc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu")]]))
    elif q.data == "int":
        context.user_data['action'] = "int"
        await q.edit_message_text("⏱ أرسل الفاصل بالدقائق:")

async def handle_inputs(update, context):
    uid = update.effective_user.id
    action = context.user_data.get('action')
    if not action: return

    with sqlite3.connect(DB_NAME) as conn:
        if action == "ch":
            conn.execute("INSERT OR IGNORE INTO channels VALUES (?,?)", (uid, update.message.text))
            await update.message.reply_text(f"✅ تمت إضافة القناة.")
        elif action == "up":
            conn.execute("INSERT INTO posts (user_id, chat_id, cap_html) VALUES (?,?,?)", (uid, context.user_data['target'], update.message.text_html))
            await update.message.reply_text("✅ تم حفظ المنشور.")
        elif action == "int" and update.message.text.isdigit():
            conn.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
            conn.execute("UPDATE settings SET interval=? WHERE user_id=?", (int(update.message.text), uid))
            await update.message.reply_text(f"✅ تم الضبط.")
        elif action == "change_sub" and uid == ADMIN_ID:
            conn.execute("UPDATE force_sub SET channel_id=? WHERE id=1", (update.message.text,))
            await update.message.reply_text(f"✅ تم تحديث قناة الاشتراك.")
        elif action == "bc" and uid == ADMIN_ID:
            users = conn.execute("SELECT DISTINCT user_id FROM settings").fetchall()
            for u in users:
                try: await context.bot.send_message(u[0], f"📢 **رسالة من الإدارة:**\n\n{update.message.text}")
                except: pass
            await update.message.reply_text("✅ تم إرسال الإذاعة.")
    
    context.user_data['action'] = None
    await menu(update, context)

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
    if not BOT_TOKEN: return print("❌ التوكن مفقود!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", menu))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inputs))
    asyncio.get_event_loop().create_task(publisher(app))
    app.run_polling()

if __name__ == "__main__":
    run()
EOF

python final_bot.py
