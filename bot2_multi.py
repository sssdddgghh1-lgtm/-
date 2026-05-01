import logging, sqlite3, asyncio, time, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.error import RetryAfter, Forbidden, BadRequest

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
    c.execute('''CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id TEXT, UNIQUE(user_id, chat_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, file_id TEXT, caption TEXT, text TEXT, channel_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, interval INTEGER DEFAULT 60, last_post_time INTEGER DEFAULT 0, is_paused INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def is_admin(user_id):
    return user_id == ADMIN_ID

init_db()
A_CH, A_INT, A_POST, A_SELECT_CH, D_CH = range(5)

def get_main_kb(user_id):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT is_paused FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    pause_text = "▶️ استئناف" if (row and row[0]) else "⏸ إيقاف مؤقت"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 إضافة قناة", callback_data="add_ch"), InlineKeyboardButton("➕ منشور جديد", callback_data="add_p")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list_ch"), InlineKeyboardButton("📊 الحالة", callback_data="stat")],
        [InlineKeyboardButton("⏱ الفاصل", callback_data="set_i"), InlineKeyboardButton(pause_text, callback_data="toggle_pause")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="del_ch"), InlineKeyboardButton("⚠️ مسح المنشورات", callback_data="confirm_del_all")]
    ])

async def show_panel(update: Update):
    uid = update.effective_user.id
    txt = "🔧 *نظام الزعيم للنشر الذكي*\n✅ الوضع: نشط وآمن"
    kb = get_main_kb(uid)
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

async def send_with_retry(func, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            wait = e.retry_after
            logging.warning(f"FloodWait: الانتظار {wait}s (محاولة {attempt+1}/{max_retries})")
            await asyncio.sleep(wait)
        except Exception as e:
            logging.error(f"فشل الإرسال: {e}")
            return None
    return None

async def save_item(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    uid = update.effective_user.id
    msg = update.message
    conn = get_db()
    c = conn.cursor()

    try:
        if mode == "ch":
            ch = msg.text.strip()
            if not ch.startswith('@') and not ch.startswith('-100'):
                await msg.reply_text("⚠️ المعرف يجب أن يبدأ بـ @ أو -100")
                return ConversationHandler.END
            c.execute("INSERT OR IGNORE INTO channels (user_id, chat_id) VALUES (?, ?)", (uid, ch))
            await msg.reply_text(f"✅ تم إضافة القناة {ch}")
            
        elif mode == "del":
            ch = msg.text.strip()
            c.execute("DELETE FROM channels WHERE user_id = ? AND chat_id = ?", (uid, ch))
            await msg.reply_text(f"🗑 تم حذف القناة {ch}" if c.rowcount else f"⚠️ القناة {ch} غير موجودة")
            
        elif mode == "post":
            # ✅ جديد: اختيار القناة أولاً
            channels = c.execute("SELECT chat_id FROM channels WHERE user_id = ?", (uid,)).fetchall()
            if not channels:
                await msg.reply_text("⚠️ لا توجد قنوات. أضف قناة أولاً.")
                return ConversationHandler.END
            
            # حفظ نوع المنشور مؤقتاً
            f_type, f_id, cap, txt = "text", None, None, None
            if msg.photo:
                f_type, f_id, cap = "photo", msg.photo[-1].file_id, msg.caption
            elif msg.video:
                f_type, f_id, cap = "video", msg.video.file_id, msg.caption
            elif msg.document:
                f_type, f_id, cap = "document", msg.document.file_id, msg.caption
            elif msg.audio:
                f_type, f_id, cap = "audio", msg.audio.file_id, msg.caption
            elif msg.voice:
                f_type, f_id, cap = "voice", msg.voice.file_id, msg.caption
            elif msg.sticker:
                f_type, f_id = "sticker", msg.sticker.file_id
            else:
                f_type, txt = "text", msg.text
            
            context.user_data['temp_post'] = (f_type, f_id, cap, txt)
            
            # عرض القنوات للاختيار
            kb_buttons = []
            for ch in channels:
                kb_buttons.append([InlineKeyboardButton(f"📢 {ch[0]}", callback_data=f"ch_{ch[0]}")])
            kb_buttons.append([InlineKeyboardButton("📡 جميع القنوات", callback_data="ch_all")])
            kb_buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_post")])
            
            await msg.reply_text("✅ تم استلام المنشور!\n\nلأي قناة تريد إرساله؟", reply_markup=InlineKeyboardMarkup(kb_buttons))
            return A_SELECT_CH
            
        elif mode == "int":
            if msg.text.isdigit():
                val = int(msg.text)
                if val < 1 or val > 1440:
                    await msg.reply_text("⚠️ الفاصل الزمني يجب أن يكون بين 1 و 1440 دقيقة")
                    return ConversationHandler.END
                c.execute("INSERT INTO user_settings (user_id, interval) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET interval=?", 
                         (uid, val, val))
                await msg.reply_text(f"⏱ تم ضبط الفاصل إلى {val} دقيقة")
            else:
                await msg.reply_text("⚠️ الرجاء إدخال رقم صحيح")
                return ConversationHandler.END

        conn.commit()
        
    except Exception as e:
        logging.error(f"خطأ في حفظ البيانات: {e}")
        await msg.reply_text("❌ حدث خطأ، يرجى المحاولة مرة أخرى")
    finally:
        conn.close()
        
    await show_panel(update)
    return ConversationHandler.END

async def auto_poster(app: Application):
    while True:
        try:
            now = int(time.time())
            conn = get_db()
            c = conn.cursor()

            users = c.execute("""
                SELECT user_id, interval FROM user_settings 
                WHERE (? - last_post_time) >= (interval * 60) AND is_paused = 0
            """, (now,)).fetchall()

            for uid, interval in users:
                # جلب جميع القنوات
                channels = [row[0] for row in c.execute("SELECT chat_id FROM channels WHERE user_id = ?", (uid,)).fetchall()]
                if not channels: continue
                
                for ch in channels:
                    # ✅ جديد: جلب منشور مخصص لهذه القناة (أو لجميع القنوات)
                    post = c.execute("""
                        SELECT type, file_id, caption, text FROM posts 
                        WHERE user_id = ? AND (channel_id = ? OR channel_id IS NULL)
                        ORDER BY RANDOM() LIMIT 1
                    """, (uid, ch)).fetchone()
                    
                    if not post:
                        continue
                    
                    f_type, f_id, cap, txt = post
                    try:
                        if f_type == "text":
                            await send_with_retry(app.bot.send_message, chat_id=ch, text=txt)
                        elif f_type == "photo":
                            await send_with_retry(app.bot.send_photo, chat_id=ch, photo=f_id, caption=cap)
                        elif f_type == "video":
                            await send_with_retry(app.bot.send_video, chat_id=ch, video=f_id, caption=cap)
                        elif f_type == "document":
                            await send_with_retry(app.bot.send_document, chat_id=ch, document=f_id, caption=cap)
                        elif f_type == "audio":
                            await send_with_retry(app.bot.send_audio, chat_id=ch, audio=f_id, caption=cap)
                        elif f_type == "voice":
                            await send_with_retry(app.bot.send_voice, chat_id=ch, voice=f_id, caption=cap)
                        elif f_type == "sticker":
                            await send_with_retry(app.bot.send_sticker, chat_id=ch, sticker=f_id)
                    except Exception as e:
                        logging.error(f"خطأ في الإرسال للقناة {ch}: {e}")
                
                # تحديث وقت النشر
                c.execute("UPDATE user_settings SET last_post_time = ? WHERE user_id = ?", (now, uid))
                conn.commit()

            conn.close()
        except Exception as e:
            logging.error(f"خطأ في المجدول: {e}")
        await asyncio.sleep(30)

async def general_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    conn = get_db()
    c = conn.cursor()

    try:
        if q.data == "toggle_pause":
            c.execute("""INSERT INTO user_settings (user_id, is_paused) 
                        VALUES (?, 1) ON CONFLICT(user_id) 
                        DO UPDATE SET is_paused = 1 - is_paused""", (uid,))
            conn.commit()
            conn.close()
            await show_panel(update)
            return

        if q.data == "confirm_del_all":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="do_del_all")],
                [InlineKeyboardButton("❌ تراجع", callback_data="main_menu")]
            ])
            await q.edit_message_text("⚠️ هل أنت متأكد من حذف جميع المنشورات؟", reply_markup=kb)
            return

        if q.data == "do_del_all":
            c.execute("DELETE FROM posts WHERE user_id = ?", (uid,))
            conn.commit()
            conn.close()
            await q.answer("🗑 تم مسح المنشورات")
            await show_panel(update)
            return

        if q.data == "list_ch":
            chs = c.execute("SELECT chat_id FROM channels WHERE user_id = ?", (uid,)).fetchall()
            conn.close()
            txt = "📭 لا توجد قنوات" if not chs else "📋 *قنواتك:*\n" + "\n".join(f"• `{r[0]}`" for r in chs)
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]), parse_mode="Markdown")
            return

        if q.data == "stat":
            posts_count = c.execute("SELECT COUNT(*) FROM posts WHERE user_id = ?", (uid,)).fetchone()[0]
            channels_count = c.execute("SELECT COUNT(*) FROM channels WHERE user_id = ?", (uid,)).fetchone()[0]
            conn.close()
            await q.edit_message_text(f"📊 الحالة:\n📦 منشورات: {posts_count}\n📢 قنوات: {channels_count}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]), parse_mode="Markdown")
            return

        if q.data == "main_menu":
            await show_panel(update)
            return
            
        # ✅ جديد: معالجة اختيار القناة للمنشور
        if q.data.startswith("ch_"):
            if q.data == "ch_all":
                context.user_data['selected_channel'] = "all"
            else:
                context.user_data['selected_channel'] = q.data[3:]
            
            # حفظ المنشور مع القناة المحددة
            temp_post = context.user_data.get('temp_post')
            if temp_post:
                f_type, f_id, cap, txt = temp_post
                selected = context.user_data.get('selected_channel')
                if selected == "all":
                    c.execute("INSERT INTO posts (user_id, type, file_id, caption, text, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                             (uid, f_type, f_id, cap, txt, None))
                    await q.edit_message_text("✅ تم حفظ المنشور لجميع القنوات")
                else:
                    c.execute("INSERT INTO posts (user_id, type, file_id, caption, text, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                             (uid, f_type, f_id, cap, txt, selected))
                    await q.edit_message_text(f"✅ تم حفظ المنشور للقناة {selected}")
                conn.commit()
                context.user_data.pop('temp_post', None)
                context.user_data.pop('selected_channel', None)
                await show_panel(update)
            return
            
        if q.data == "cancel_post":
            context.user_data.pop('temp_post', None)
            context.user_data.pop('selected_channel', None)
            await q.edit_message_text("❌ تم إلغاء إضافة المنشور")
            await show_panel(update)
            return
            
    except Exception as e:
        logging.error(f"خطأ في معالجة callback: {e}")
    finally:
        if conn:
            conn.close()

async def conv_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    prompts = {"add_ch": "📢 أرسل المعرف:", "add_p": "➕ أرسل المنشور:", "set_i": "⏱ أرسل الدقائق:", "del_ch": "🗑 أرسل المعرف للحذف:"}
    await q.edit_message_text(prompts[q.data])
    return {"add_ch": A_CH, "add_p": A_POST, "set_i": A_INT, "del_ch": D_CH}[q.data]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_panel(update)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.")
    await show_panel(update)
    return ConversationHandler.END

async def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(general_callback, pattern="^(toggle_pause|confirm_del_all|do_del_all|list_ch|stat|main_menu|ch_|ch_all|cancel_post)$"))
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(conv_entry, pattern="^(add_ch|add_p|set_i|del_ch)$")],
        states={
            A_CH: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: save_item(u, c, "ch"))],
            A_INT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: save_item(u, c, "int"))],
            A_POST: [MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_item(u, c, "post"))],
            A_SELECT_CH: [CallbackQueryHandler(general_callback, pattern="^(ch_|ch_all|cancel_post)$")],
            D_CH: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: save_item(u, c, "del"))],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    
    async with app:
        await app.initialize()
        await app.start()
        asyncio.create_task(auto_poster(app))
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
