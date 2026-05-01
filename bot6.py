import logging, asyncio, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

logging.basicConfig(level=logging.INFO)

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
    elif data == "post":
        await query.edit_message_text("✅ زر المنشور اشتغل")
    elif data == "list":
        await query.edit_message_text("✅ زر قنواتي اشتغل")
    elif data == "stat":
        await query.edit_message_text("✅ زر الحالة اشتغل")
    elif data == "int":
        await query.edit_message_text("✅ زر الفاصل اشتغل")
    elif data == "pause":
        await query.edit_message_text("✅ زر الايقاف اشتغل")
    elif data == "del":
        await query.edit_message_text("✅ زر الحذف اشتغل")
    else:
        await query.edit_message_text("❌ زر غير معروف")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
