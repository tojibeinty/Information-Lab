from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# توكن البوت
BOT_TOKEN = "8402805384:AAG-JnszBhh8GMDIvf1oeKNUvXi07MOXSWo"

# معرف الأدمن
ADMIN_ID = 6263195701

# قاعدة بيانات التحاليل
tests_db = {
    "CBC": {
        "full_name": "Complete Blood Count",
        "description": "تحليل شامل لقياس مكونات الدم وتقييم الصحة العامة.",
        "normal_range": {
            "male": "4.7-6.1",
            "female": "4.2-5.4",
            "children": "4.1-5.5",
            "newborn": "4.8-7.1",
            "elderly": "4.0-5.2"
        },
        "image": None
    }
}

user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for test in tests_db.keys():
        buttons = [InlineKeyboardButton(test, callback_data=f"test:{test}")]
        if update.effective_chat.id == ADMIN_ID:
            buttons.append(InlineKeyboardButton("حذف", callback_data=f"delete:{test}"))
        keyboard.append(buttons)

    if update.effective_chat.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("إضافة تحليل", callback_data="add_test")])

    await update.message.reply_text(
        "اختر التحليل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("test:"):
        _, test_name = data.split(":")
        data_test = tests_db.get(test_name)
        if not data_test:
            await query.answer("لا يوجد هذا التحليل.")
            return
        
        msg = f"التحليل: {data_test['full_name']}\nالوصف: {data_test['description']}\nالنطاق الطبيعي:\n"
        labels = {"male": "ذكر", "female": "أنثى", "children": "أطفال", "newborn": "حديث الولادة", "elderly": "كبار السن"}
        for k, v in data_test["normal_range"].items():
            label = labels.get(k, k)
            msg += f"{label}: {v}\n"

        await context.bot.send_message(chat_id, msg)
        await query.answer()
        return

    elif data.startswith("delete:"):
        if chat_id != ADMIN_ID:
            await query.answer("للأدمن فقط.", show_alert=True)
            return
        _, test_name = data.split(":")
        if test_name in tests_db:
            del tests_db[test_name]
            await query.edit_message_text(f"تم حذف التحليل: {test_name}")
        else:
            await query.answer("التحليل غير موجود.")
        return

    elif data == "add_test":
        if chat_id != ADMIN_ID:
            await query.answer("الأمر للأدمن فقط.", show_alert=True)
            return
        user_states[chat_id] = {"step": "name"}
        await context.bot.send_message(chat_id, "أدخل اسم التحليل (قصير):")
        await query.answer()

async def add_test_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id != ADMIN_ID:
        return

    if chat_id not in user_states:
        return

    step = user_states[chat_id]["step"]

    if step == "name":
        user_states[chat_id]["short_name"] = update.message.text
        user_states[chat_id]["step"] = "full_name"
        await update.message.reply_text("أدخل الاسم العلمي الكامل:")
    
    elif step == "full_name":
        user_states[chat_id]["full_name"] = update.message.text
        user_states[chat_id]["step"] = "description"
        await update.message.reply_text("أدخل وصف التحليل:")
    
    elif step == "description":
        user_states[chat_id]["description"] = update.message.text
        user_states[chat_id]["step"] = "normal_range"
        user_states[chat_id]["normal_range"] = {}
        await update.message.reply_text("أدخل النطاق الطبيعي للذكور (مثال: 4.7-6.1):")
    
    elif step == "normal_range":
        nr = user_states[chat_id]["normal_range"]
        text = update.message.text.strip()
        if not validate_range(text):
            await update.message.reply_text("أدخل النطاق بالأرقام فقط، مثال: 4.7-6.1")
            return

        if "male" not in nr:
            nr["male"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي للإناث:")
        elif "female" not in nr:
            nr["female"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي للأطفال:")
        elif "children" not in nr:
            nr["children"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي لحديثي الولادة:")
        elif "newborn" not in nr:
            nr["newborn"] = text
            await update.message.reply_text("أدخل النطاق الطبيعي لكبار السن:")
        elif "elderly" not in nr:
            nr["elderly"] = text
            tests_db[user_states[chat_id]["short_name"]] = {
                "full_name": user_states[chat_id]["full_name"],
                "description": user_states[chat_id]["description"],
                "normal_range": nr,
                "image": None
            }
            await update.message.reply_text("تم حفظ التحليل.")
            del user_states[chat_id]

def validate_range(text):
    import re
    return bool(re.match(r"^\d+(\.\d+)?-\d+(\.\d+)?$", text))

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_test_steps))

    app.run_polling()

if __name__ == "__main__":
    main()
