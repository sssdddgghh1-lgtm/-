import asyncio, os
from telegram import Bot

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("export BOT_TOKEN='token'")
    exit()

async def test():
    bot = Bot(BOT_TOKEN)
    # جرب ترسل رسالة لقناتك (غير @test إلى معرف قناتك)
    await bot.send_message(chat_id="@test", text="اختبار من البوت")
    print("✅ تم الإرسال")

asyncio.run(test())
