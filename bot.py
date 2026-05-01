import telebot
from telebot import types

# الإعدادات الأساسية
API_TOKEN = '8295665183:AAHERIriMQMc_x8Mz-_x5I8Ef87JB8Wnvyo'
ADMIN_ID = 7983340250
CHANNEL_ID = '@zzimmiie'

bot = telebot.TeleBot(API_TOKEN)

# قائمة المحظورين
banned_users = set()

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    
    if uid in banned_users:
        bot.send_message(message.chat.id, "❌ أنت محظور من استخدام البوت.")
        return

    if is_subscribed(uid):
        # الأزرار الشفافة
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        btn1 = types.InlineKeyboardButton("📝 إضافة منشور", callback_data="add_post")
        btn2 = types.InlineKeyboardButton("📢 قنوات النشر", callback_data="channels")
        btn3 = types.InlineKeyboardButton("📊 الحالة", callback_data="status")
        btn4 = types.InlineKeyboardButton("⏱️ الفاصل", callback_data="timer")
        btn5 = types.InlineKeyboardButton("⚙️ ضبط الاشتراك الإجباري", callback_data="sub_settings")
        btn6 = types.InlineKeyboardButton("📣 إذاعة للكل", callback_data="broadcast")
        
        markup.add(btn1, btn2)
        markup.add(btn3, btn4)
        markup.add(btn5)
        markup.add(btn6)
        
        if uid == ADMIN_ID:
            markup.add(types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="block_user"))
            
        bot.send_message(message.chat.id, "💎 **لوحة تحكم النشر التلقائي** 💎\n\n✅ أهلاً بك يا زعيم، البوت جاهز للعمل!", parse_mode="Markdown", reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_ID[1:]}"))
        markup.add(types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check"))
        bot.send_message(message.chat.id, f"⚠️ يجب الاشتراك في {CHANNEL_ID} أولاً لتفعيل البوت.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "check":
        if is_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ تم التحقق!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "تم استلام الأمر ✅")

print("--- تم استعادة النسخة الشغالة والمستقرة بنجاح ---")
bot.infinity_polling()
