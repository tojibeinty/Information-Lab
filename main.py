from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re

# ===== إعدادات البوت =====
BOT_TOKEN = "8402805384:AAG-JnszBhh8GMDIvf1oeKNUvXi07MOXSWo"
ADMIN_ID = 6263195701
INSTAGRAM_LINK = "https://instagram.com/tojibeinty"

# قاعدة بيانات التحاليل
tests_db = {
    "مناعية": {},
    "دم": {},
    "كيميا": {},
    "هرمونات": {}
}

# حالة المستخدم أثناء الإضافة أو إدارة الأقسام
user_states = {}

# ===== دوال البوت =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "مرحباً بك في بوت التحاليل الطبية.\n"
        "يمكنك هنا استعراض التحاليل الطبية مع النطاق الطبيعي لكل منها.\n\n"
        f"📌 تابعني على إنستغرام: {INSTAGRAM_LINK}"
    )
    keyboard = [
        [InlineKeyboardButton("التحاليل", callback_data="categories")]
    ]
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:  # استدعاء من زر الرجوع
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
        await update.callback_query.answer()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    # زر الرجوع للقائمة الرئيسية
    if data == "start_menu":
        await start(update, context)
        return

    # قائمة الأقسام
    elif data == "categories":
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"category:{cat}")] for cat in tests_db.keys()]
        if chat_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("إضافة تحليل", callback_data="add_test")])
            keyboard.append([InlineKeyboardButton("إضافة قسم", callback_data="add_category")])
            keyboard.append([InlineKeyboardButton("حذف قسم", callback_data="delete_category")])
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="start_menu")])
        await query.edit_message_text("اختر القسم:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()

    # عرض التحاليل داخل القسم
    elif data.startswith("category:"):
        _, category = data.split(":")
        keyboard = []
        for test in tests_db[category]:
            btns = [InlineKeyboardButton(test, callback_data=f"test:{category}:{test}")]
            if chat_id == ADMIN_ID:
                btns.append(InlineKeyboardButton("حذف", callback_data=f"delete:{category}:{test}"))
            keyboard.append(btns)
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="categories")])
        await query.edit_message_text(f"قسم: {category}", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()

    # عرض تفاصيل التحليل
    elif data.startswith("test:"):
        _, category, test_name = data.split(":")
        test_data = tests_db[category].get(test_name)
        if not test_data:
            await query.answer("لا يوجد هذا التحليل.")
            return
        msg = f"التحليل: {test_data['full_name']}\nالوصف: {test_data['description']}\n\nالنطاق الطبيعي:\n"
        labels = {"male": "ذكر", "female": "أنثى", "children": "أطفال", "newborn": "حديث الولادة", "elderly": "كبار السن"}
        for k, v in test_data["normal_range"].items():
            msg += f"{labels[k]}: {v}\n"
        await context.bot.send_message(chat_id, msg)
        await query.answer()

    # حذف تحليل
    elif data.startswith("delete:") and chat_id == ADMIN_ID:
        _, category, test_name = data.split(":")
        if test_name in tests_db[category]:
            del tests_db[category][test_name]
            await query.edit_message_text(f"تم حذف التحليل: {test_name}")
        else:
            await query.answer("التحليل غير موجود.")

    # إضافة تحليل
    elif data == "add_test" and chat_id == ADMIN_ID:
        user_states[chat_id] = {"step": "choose_category"}
        cats_keyboard = [[InlineKeyboardButton(cat, callback_data=f"choosecat:{cat}")] for cat in tests_db.keys()]
        cats_keyboard.append([InlineKeyboardButton("رجوع", callback_data="categories")])
        await context.bot.send_message(chat_id, "اختر القسم الذي تريد إضافة التحليل إليه:", reply_markup=InlineKeyboardMarkup(cats_keyboard))

    elif data.startswith("choosecat:") and chat_id == ADMIN_ID:
        _, cat = data.split(":")
        user_states[chat_id] = {"step": "name", "category": cat}
        await context.bot.send_message(chat_id, "أدخل اسم التحليل (قصير):")
        await query.answer()

    # إضافة قسم
    elif data == "add_category" and chat_id == ADMIN_ID:
        user_states[chat_id] = {"step": "add_category_name"}
        await context.bot.send_message(chat_id, "أدخل اسم القسم الجديد:")

    # حذف قسم
    elif data == "delete_category" and chat_id == ADMIN_ID:
        if not tests_db:
            await query.answer("لا توجد أقسام للحذف.")
            return
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"delcat:{cat}")] for cat in tests_db.keys()]
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="categories")])
        await context.bot.send_message(chat_id, "اختر القسم الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delcat:") and chat_id == ADMIN_ID:
        _, cat = data.split(":")
        if cat in tests_db:
            del tests_db[cat]
            await query.edit_message_text(f"تم حذف القسم: {cat} وجميع التحاليل بداخله.")
        else:
            await query.answer("القسم غير موجود.")

async def add_test_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id != ADMIN_ID or chat_id not in user_states:
        return

    step = user_states[chat_id]["step"]

    # خطوات إضافة التحليل
    if step == "name":
        user_states[chat_id]["short_name"] = update.message.text.strip()
        user_states[chat_id]["step"] = "full_name"
        await update.message.reply_text("أدخل الاسم العلمي الكامل:")

    elif step == "full_name":
        user_states[chat_id]["full_name"] = update.message.text.strip()
        user_states[chat_id]["step"] = "description"
        await update.message.reply_text("أدخل وصف التحليل:")

    elif step == "description":
        user_states[chat_id]["description"] = update.message.text.strip()
        user_states[chat_id]["step"] = "normal_range"
        user_states[chat_id]["normal_range"] = {}
        await update.message.reply_text("أدخل النطاق الطبيعي للذكور (مثال: 4.7-6.1):")

    elif step == "normal_range":
        nr = user_states[chat_id]["normal_range"]
        text = update.message.text.strip()
        if not validate_range(text):
            await update.message.reply_text("أدخل النطاق بالأرقام فقط مثل: 4.7-6.1")
            return
        if "male" not in nr:
            nr["male"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي للإناث:")
        elif "female" not in nr:
            nr["female"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي للأطفال:")
        elif "children" not in nr:
            nr["children"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي لحديث الولادة:")
        elif "newborn" not in nr:
            nr["newborn"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي لكبار السن:")
        elif "elderly" not in nr:
            nr["elderly"] = text
            cat = user_states[chat_id]["category"]
            tests_db[cat][user_states[chat_id]["short_name"]] = {
                "full_name": user_states[chat_id]["full_name"],
                "description": user_states[chat_id]["description"],
                "normal_range": nr
            }
            await update.message.reply_text("تم حفظ التحليل.")
            del user_states[chat_id]

    # خطوات إضافة قسم
    elif step == "add_category_name":
        category_name = update.message.text.strip()
        if category_name in tests_db:
            await update.message.reply_text("هذا القسم موجود مسبقاً!")
        else:
            tests_db[category_name] = {}
            await update.message.reply_text(f"تم إضافة القسم: {category_name}")
        del user_states[chat_id]

def validate_range(text):
    return bool(re.match(r"^\s*\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*$", text))

# ===== تشغيل البوت =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_test_steps))
    app.run_polling()

if __name__ == "__main__":
    main()
