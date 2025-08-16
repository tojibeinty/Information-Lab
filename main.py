from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
import re

# ===== إعدادات البوت =====
BOT_TOKEN = "8402805384:AAFkyqNHUbDz5DDbBXoZOgv4Ve81Nd510vk"
ADMIN_ID = 6263195701
INSTAGRAM_LINK = "https://instagram.com/tojibeinty"

# ===== الملفات =====
USERS_FILE = "members.json"
TESTS_FILE = "tests_db.json"

# ===== تحميل البيانات =====
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        members = set(json.load(f))
else:
    members = set()

if os.path.exists(TESTS_FILE):
    with open(TESTS_FILE, "r", encoding="utf-8") as f:
        try:
            tests_db = json.load(f)
        except json.JSONDecodeError:
            tests_db = {}
            print("خطأ في ملف tests_db.json")
else:
    tests_db = {}

# ===== حفظ البيانات =====
def save_members():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(members), f, ensure_ascii=False, indent=2)

def save_tests_db():
    with open(TESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(tests_db, f, ensure_ascii=False, indent=2)

# ===== حالة المستخدم =====
user_states = {}

# ===== دوال مساعدة =====
def build_buttons_list(items, category):
    """إنشاء أزرار InlineKeyboardButton بصفين لكل صف زرين"""
    keyboard = []
    row = []
    for i, item in enumerate(items, 1):
        row.append(InlineKeyboardButton(item, callback_data=f"test:{category}:{item}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

# ===== دوال البوت =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    if chat_id not in members:
        members.add(chat_id)
        save_members()

    welcome_text = (
        "مرحباً بك في بوت التحاليل الطبية.\n"
        "يمكنك هنا استعراض التحاليل الطبية مع النطاق الطبيعي لكل منها.\n\n"
        f"📌 تابعني على إنستغرام: {INSTAGRAM_LINK}"
    )
    keyboard = [[InlineKeyboardButton("التحاليل", callback_data="categories")]]
    if chat_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("عدد الأعضاء", callback_data="member_count")])
        keyboard.append([InlineKeyboardButton("إرسال رسالة جماعية", callback_data="broadcast")])

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
        await update.callback_query.answer()

# ===== التعامل مع الأزرار =====
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    if data == "start_menu":
        await start(update, context)
        return

    elif data == "member_count" and chat_id == ADMIN_ID:
        await query.answer()
        await context.bot.send_message(chat_id, f"عدد الأعضاء الحالي: {len(members)}")
        return

    elif data == "broadcast" and chat_id == ADMIN_ID:
        user_states[chat_id] = {"step": "broadcast"}
        await context.bot.send_message(chat_id, "أرسل الرسالة التي تريد إرسالها لجميع الأعضاء:")
        await query.answer()
        return

    elif data == "categories":
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"category:{cat}")] for cat in tests_db.keys()]
        if chat_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("إضافة تحليل", callback_data="add_test")])
            keyboard.append([InlineKeyboardButton("إضافة قسم", callback_data="add_category")])
            keyboard.append([InlineKeyboardButton("حذف قسم", callback_data="delete_category")])
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="start_menu")])
        await query.edit_message_text("اختر القسم:", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()

    elif data.startswith("category:"):
        _, category = data.split(":")
        category = category.strip()
        if category not in tests_db:
            await query.answer("القسم غير موجود.")
            return
        test_names = list(tests_db[category].keys())
        keyboard = build_buttons_list(test_names, category)
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="categories")])
        await query.edit_message_text(f"قسم: {category}", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()

    elif data.startswith("test:"):
        _, category, test_name = data.split(":")
        test_data = tests_db.get(category, {}).get(test_name)
        if not test_data:
            await query.answer("لا يوجد هذا التحليل.")
            return
        msg = f"التحليل: {test_data['full_name']}\nالوصف: {test_data['description']}\n\nالنطاق الطبيعي:\n"
        labels = {"male": "ذكر", "female": "أنثى", "children": "أطفال", "newborn": "حديث الولادة", "elderly": "كبار السن"}
        for k, v in test_data["normal_range"].items():
            msg += f"{labels[k]}: {v}\n"
        await context.bot.send_message(chat_id, msg)
        await query.answer()

    elif data.startswith("delete:") and chat_id == ADMIN_ID:
        _, category, test_name = data.split(":")
        if test_name in tests_db.get(category, {}):
            del tests_db[category][test_name]
            save_tests_db()
            await query.edit_message_text(f"تم حذف التحليل: {test_name}")
        else:
            await query.answer("التحليل غير موجود.")

# ===== التعامل مع الرسائل النصية =====
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in user_states:
        return

    step = user_states[chat_id]["step"]

    if step == "broadcast":
        msg = update.message.text
        for member_id in members:
            try:
                await context.bot.send_message(member_id, msg)
            except:
                pass
        await update.message.reply_text("تم إرسال الرسالة لجميع الأعضاء.")
        del user_states[chat_id]

# ===== تشغيل البوت =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.run_polling()

if __name__ == "__main__":
    main()
