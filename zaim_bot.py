import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- إعدادات الزعيم ---
BOT_TOKEN = "8283445793:AAH-pZAxASOEvwpcTDvCNxyMTmFTiI3M1Ls"
GEMINI_KEY = "AIzaSyAHr7UEXtbUN46Y1I3z3CqrfGG-fQNVXbY"
CHANNEL_ID = "@Zaim_Yemen" 
ADMIN_ID = 7983340250

logging.basicConfig(level=logging.INFO)

# --- محرك الذكاء الاصطناعي (تحديث الرابط لـ latest) ---
def ask_gemini(question):
    # تم تغيير الموديل إلى gemini-1.5-flash-latest لضمان العثور عليه
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"أنت مساعد ذكي ومحترف اسمك 'بوت الزعيم'. أجب بذكاء واختصار على: {question}"}]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response_data = response.json()
        
        if 'candidates' in response_data and response_data['candidates']:
            return response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            # إذا استمر الخطأ، سيطبع التفاصيل في الترمكس لنعرف السبب
            print(f"❌ رد جوجل: {response_data}")
            return "يا زعيم، أحتاج لتعديل بسيط، جرب تسألني مرة ثانية."
    except Exception as e:
        print(f"❌ خطأ اتصال: {e}")
        return "مشكلة في الشبكة، تأكد من إنترنت الجوال."

# --- نظام الاشتراك الإجباري ---
async def check_sub(uid, context):
    if uid == ADMIN_ID: return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await check_sub(uid, context):
        keyboard = [[InlineKeyboardButton("📢 اشترك في القناة هنا", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🛡️ **مرحباً بك في بوت الزعيم**\n\nاشترك في القناة لتفعيل الذكاء الاصطناعي:\n🔗 {CHANNEL_ID}", reply_markup=reply_markup, parse_mode="Markdown")
        return
    await update.message.reply_text("😎 **تم التفعيل!** أنا مربوط الآن بذكاء Gemini. اسألني أي شيء.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await check_sub(uid, context):
        await update.message.reply_text(f"⚠️ اشترك أولاً: {CHANNEL_ID}")
        return
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    answer = ask_gemini(user_text)
    await update.message.reply_text(answer)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 تم تحديث الرابط لـ Flash-Latest! البوت جاهز.")
    app.run_polling()

if __name__ == "__main__":
    main()

