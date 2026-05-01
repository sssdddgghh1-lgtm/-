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
        [InlineKeyboardButton("✅ اختبرني", callback_data="test")],
        [InlineKeyboardButton("📋 قنواتي", callback_data="list")],
        [InlineKeyboardButton("📊 حالة", callback_data="stat")]
    ])
    await update.message.reply_text("🔧 اضغط على زر:", reply_markup=kb)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "test":
        await query.edit_message_text("✅ الزر اشتغل! البوت شغال.")
    elif query.data == "list":
        await query.edit_message_text("📋 قائمة القنوات: (لا توجد)")
    elif query.data == "stat":
        await query.edit_message_text("📊 البوت شغال 100%")

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
