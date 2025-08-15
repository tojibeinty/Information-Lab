import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

DB_PATH = "./users_db.json"
TESTS_PATH = "./tests_db.json"
ADMINS = [6263195701]  # ضع هنا رقم تليجرامك

# ========= إدارة البيانات ==========
def load_db(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(db, path):
    with open(path, "w") as f:
        json.dump(db, f, indent=2)

users = load_db(DB_PATH)
tests_db = load_db(TESTS_PATH)

def get_user(chat_id):
    chat_id = str(chat_id)
    if chat_id not in users:
        users[chat_id] = {
            "awaiting_test": None,
            "adding_step": None,
            "new_test": {},
            "category": None
        }
    return users[chat_id]

# ========= الكيبورد ==========
def kb_category_root():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(cat["title"], callback_data=f"cat:{key}")]
        for key, cat in CATEGORIES.items()
    ])

def kb_tests_for(category_key):
    cat = CATEGORIES.get(category_key)
    if not cat:
        return kb_category_root()
    buttons = [[InlineKeyboardButton(test, callback_data=f"test:{test}")] for test in cat["tests"]]
    buttons.append([InlineKeyboardButton("🔙 الأنواع", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

# ========= التصنيفات ==========
CATEGORIES = {
    "CBC":{"title":"🩸 تحاليل الدم","tests":["WBC","RBC","Hb","Hct","Platelets"]},
    "CHEM":{"title":"🧪 كيمياء","tests":["FastingGlucose","RandomGlucose","Urea","Creatinine","ALT","AST"]},
    "HORM":{"title":"🔥 هرمونات","tests":["TSH","FreeT4","Prolactin","Testosterone"]},
}

# ========= أوامر البوت ==========
def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id, "👋 أهلاً بك! اختر نوع التحليل:", reply_markup=kb_category_root())

def add_test(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        context.bot.send_message(chat_id, "❌ لا يمكنك استخدام هذا الأمر.")
        return
    u = get_user(chat_id)
    u["adding_step"] = "name"
    u["new_test"] = {}
    context.bot.send_message(chat_id, "📝 أدخل اسم التحليل الجديد (مثال: Hemoglobin):")

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text = update.message.text
    u = get_user(chat_id)

    # ===== إضافة تحليل جديد خطوة بخطوة =====
    if u.get("adding_step"):
        step = u["adding_step"]
        if step=="name":
            u["new_test"]["name"] = text
            u["adding_step"] = "full_name"
            context.bot.send_message(chat_id, "أدخل الاسم العلمي الكامل للتحليل:")
            return
        elif step=="full_name":
            u["new_test"]["full_name"] = text
            u["adding_step"] = "description"
            context.bot.send_message(chat_id, "أدخل وصف/شرح التحليل علميًا:")
            return
        elif step=="description":
            u["new_test"]["description"] = text
            u["adding_step"] = "normal_range"
            u["new_test"]["normal_range"] = {}
            context.bot.send_message(chat_id, "أدخل النطاق الطبيعي للذكر (مثال: 13-17 g/dL):")
            u["range_step"] = "male"
            return
        elif step=="normal_range":
            u["new_test"]["normal_range"][u["range_step"]] = text
            # تحديد الفئة التالية
            next_step = {"male":"female","female":"children","children":"newborn","newborn":"elderly"}
            if u["range_step"] in next_step:
                u["range_step"] = next_step[u["range_step"]]
                context.bot.send_message(chat_id, f"أدخل النطاق الطبيعي لـ {u['range_step']}:")
                return
            else:
                u["adding_step"] = "image"
                context.bot.send_message(chat_id, "أدخل اسم ملف الصورة إذا كان CBC أو بول (مثال: cbc.jpg)، أو 'none' إذا لا يوجد صورة:")
                return
        elif step=="image":
            u["new_test"]["image"] = None if text.lower()=="none" else text
            # التصنيف
            u["adding_step"] = "category"
            context.bot.send_message(chat_id, "أدخل التصنيف: CBC / CHEM / HORM")
            return
        elif step=="category":
            if text not in ["CBC","CHEM","HORM"]:
                context.bot.send_message(chat_id,"❌ التصنيف غير صحيح. أعد المحاولة.")
                return
            u["new_test"]["category"] = text
            # حفظ التحليل
            name = u["new_test"]["name"]
            tests_db[name] = {
                "full_name": u["new_test"]["full_name"],
                "description": u["new_test"]["description"],
                "normal_range": u["new_test"]["normal_range"],
                "image": u["new_test"]["image"]
            }
            # تحديث التصنيف
            cat = u["new_test"]["category"]
            if name not in CATEGORIES[cat]["tests"]:
                CATEGORIES[cat]["tests"].append(name)
            save_db(tests_db, TESTS_PATH)
            u["adding_step"]=None
            u["new_test"]={}
            context.bot.send_message(chat_id,f"✅ تم إضافة التحليل {name} بنجاح تحت {cat}")
            return

    # ===== التعامل مع عرض التحاليل =====
    if u.get("awaiting_test"):
        test_name = u["awaiting_test"]
        data = tests_db.get(test_name)
        if not data:
            context.bot.send_message(chat_id,"❌ لا يوجد هذا التحليل.")
            u["awaiting_test"]=None
            return
        msg = f"🔹 التحليل: {data['full_name']}\n💡 الوصف: {data['description']}\n📊 النطاق الطبيعي:\n"
        for k,v in data["normal_range"].items():
            emoji = {"male":"👨 ذكر","female":"👩 أنثى","children":"🧒 أطفال","newborn":"👶 حديث الولادة","elderly":"👵 كبار السن"}.get(k,k)
            msg += f"{emoji}: {v}\n"
        # إرسال الصورة إذا موجودة
        if data.get("image"):
            try:
                context.bot.send_photo(chat_id, photo=open(data["image"],"rb"), caption=msg)
            except:
                context.bot.send_message(chat_id,msg)
        else:
            context.bot.send_message(chat_id,msg)
        u["awaiting_test"]=None
        return

# ========= التعامل مع الأزرار ==========
def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data
    u = get_user(chat_id)

    if data=="home":
        query.answer()
        query.edit_message_text("اختر التصنيف:", reply_markup=kb_category_root())
        return
    if data.startswith("cat:"):
        _,cat = data.split(":")
        query.answer()
        query.edit_message_text(f"{CATEGORIES[cat]['title']} — اختر التحليل:", reply_markup=kb_tests_for(cat))
        return
    if data.startswith("test:"):
        _,test = data.split(":")
        u["awaiting_test"] = test
        query.answer()
        context.bot.send_message(chat_id,"🔹 التحليل المحدد. اضغط /start لإظهار التفاصيل.")
        return

# ========= تشغيل البوت ==========
def main():
    updater = Updater("8402805384:AAG-JnszBhh8GMDIvf1oeKNUvXi07MOXSWo", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addtest", add_test))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_callback))

    updater.start_polling()
    updater.idle()

if __name__=="__main__":
    main()
