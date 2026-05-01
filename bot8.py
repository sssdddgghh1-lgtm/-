import logging, asyncio, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

logging.basicConfig(level=logging.INFO)

POST, INTERVAL, DELETE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ قناة", callback_data="ch")],
        [InlineKeyboardButton("➕ منشور", callback_data="post")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list")],
        [InlineKeyboardButton("📊 حالة", callback_data="stat")],
        [InlineKeyboardButton("⏱ فاصل", callback_data="int")],
        [InlineKeyboardButton("⏸ ايقاف", callback_data="pause")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="del")]
    ])
    await update.message.reply_text("🔧 بوت النشر", reply_markup=kb)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # الأزرار التي ترد مباشرة
    if data == "ch":
        await query.edit_message_text("➕ قناة: أرسل معرف القناة")
        return
    elif data == "list":
        await query.edit_message_text("📋 قنواتي: لا توجد قنوات")
        return
    elif data == "stat":
        await query.edit_message_text("📊 الحالة: 0 منشورات، 0 قنوات")
        return
    elif data == "pause":
        await query.edit_message_text("⏸ تم ايقاف النشر")
        return
    
    # الأزرار التي تحتاج إدخال
    elif data == "post":
        await query.edit_message_text("➕ منشور: أرسل المنشور (نص، صورة، فيديو)")
        return POST
    elif data == "int":
        await query.edit_message_text("⏱ الفاصل: أرسل عدد الدقائق (1-1440)")
        return INTERVAL
    elif data == "del":
        await query.edit_message_text("🗑 حذف قناة: أرسل معرف القناة")
        return DELETE
    
    return ConversationHandler.END

async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم استلام المنشور")
    await start(update, context)
    return ConversationHandler.END

async def handle_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.isdigit() and 1 <= int(text) <= 1440:
        await update.message.reply_text(f"✅ تم ضبط الفاصل إلى {text} دقيقة")
    else:
        await update.message.reply_text("❌ خطأ: الرجاء إرسال رقم بين 1 و 1440")
    await start(update, context)
    return ConversationHandler.END

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ تم حذف القناة {update.message.text}")
    await start(update, context)
    return ConversationHandler.END

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern="^(post|int|del)$")],
        states={
            POST: [MessageHandler(filters.ALL, handle_post)],
            INTERVAL: [MessageHandler(filters.TEXT, handle_interval)],
            DELETE: [MessageHandler(filters.TEXT, handle_delete)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(ch|list|stat|pause)$"))
    app.add_handler(conv)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
