import logging, asyncio, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

logging.basicConfig(level=logging.INFO)

WAITING_POST = 1
WAITING_INTERVAL = 2
WAITING_DELETE = 3

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
    await update.message.reply_text("🔧 بوت النشر\nاختر من الأزرار:", reply_markup=kb)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "ch":
        await query.edit_message_text("✅ زر القناة اشتغل")
    elif data == "list":
        await query.edit_message_text("✅ زر قنواتي اشتغل")
    elif data == "stat":
        await query.edit_message_text("✅ زر الحالة اشتغل")
    elif data == "pause":
        await query.edit_message_text("✅ زر الايقاف اشتغل")
    elif data == "post":
        await query.edit_message_text("ارسل المنشور:")
        return WAITING_POST
    elif data == "int":
        await query.edit_message_text("ارسل عدد الدقائق (1-1440):")
        return WAITING_INTERVAL
    elif data == "del":
        await query.edit_message_text("ارسل معرف القناة للحذف:")
        return WAITING_DELETE
    return ConversationHandler.END

async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم استلام المنشور")
    await start(update, context)
    return ConversationHandler.END

async def handle_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.isdigit() and 1 <= int(text) <= 1440:
        await update.message.reply_text(f"✅ تم ضبط الفاصل {text} دقيقة")
    else:
        await update.message.reply_text("❌ خطأ: ارسل رقم بين 1 و 1440")
    await start(update, context)
    return ConversationHandler.END

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ تم حذف {update.message.text}")
    await start(update, context)
    return ConversationHandler.END

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern="^(post|int|del)$")],
        states={
            WAITING_POST: [MessageHandler(filters.ALL, handle_post)],
            WAITING_INTERVAL: [MessageHandler(filters.TEXT, handle_interval)],
            WAITING_DELETE: [MessageHandler(filters.TEXT, handle_delete)],
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
