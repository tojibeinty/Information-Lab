import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== إعداد البيانات ==========
DB_PATH = "./users_db.json"
TESTS_PATH = "./tests_db.json"
ADMINS = [6263195701]  # ضع هنا رقمك في تلغرام

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
        }
    return users[chat_id]

# ========== التصنيفات ==========
CATEGORIES = {
    "CBC":{"title":"🩸 تحاليل الدم","tests":["WBC","RBC","Hb","Hct","Platelets"]},
    "CHEM":{"title":"🧪 كيمياء","tests":["FastingGlucose","RandomGlucose","Urea","Creatinine","ALT","AST"]},
    "HORM":{"title":"🔥 هرمونات","tests":["TSH","FreeT4","Prolactin","Testosterone"]},
}

# ========== كيبورد ==========
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

# ========== أوامر البوت ==========
async def start(update, context):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, "👋 أهلاً بك! اختر نوع التحليل:", reply_markup=kb_category_root())

async def add_test(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        await context.bot.send_message(chat_id, "❌ لا يمكنك استخدام هذا الأمر.")
        return
    u = get_user(chat_id)
    u["adding_step"] = "name"
    u["new_test"] = {}
    await context.bot.send_message(chat_id, "📝 أدخل اسم التحليل الجديد:")

# ========== التعامل مع الرسائل ==========
async def handle_message(update, context):
    chat_id = update.effective_chat.id
    text = update.message.text
    u = get_user(chat_id)

    # ---- إضافة تحليل جديد ----
    if u.get("adding_step"):
        step = u["adding_step"]
        if step=="name":
            u["new_test"]["name"] = text
            u["adding_step"]="full_name"
            await context.bot.send_message(chat_id,"أدخل الاسم العلمي الكامل:")
            return
        elif step=="full_name":
            u["new_test"]["full_name"]=text
            u["adding_step"]="description"
            await context.bot.send_message(chat_id,"أدخل وصف التحليل علميًا:")
            return
        elif step=="description":
            u["new_test"]["description"]=text
            u["adding_step"]="normal_range"
            u["new_test"]["normal_range"] = {}
            u["range_step"]="male"
            await context.bot.send_message(chat_id,"أدخل النطاق الطبيعي للذكر (مثال: 13-17 g/dL):")
            return
        elif step=="normal_range":
            u["new_test"]["normal_range"][u["range_step"]] = text
            next_step = {"male":"female","female":"children","children":"newborn","newborn":"elderly"}
            if u["range_step"] in next_step:
                u["range_step"]=next_step[u["range_step"]]
                await context.bot.send_message(chat_id,f"أدخل النطاق الطبيعي لـ {u['range_step']}:")
                return
            else:
                u["adding_step"]="image"
                await context.bot.send_message(chat_id,"أدخل اسم ملف الصورة أو 'none':")
                return
        elif step=="image":
            u["new_test"]["image"]=None if text.lower()=="none" else text
            u["adding_step"]="category"
            await context.bot.send_message(chat_id,"أدخل التصنيف: CBC / CHEM / HORM")
            return
        elif step=="category":
            if text not in ["CBC","CHEM","HORM"]:
                await context.bot.send_message(chat_id,"❌ التصنيف غير صحيح.")
                return
            u["new_test"]["category"]=text
            name = u["new_test"]["name"]
            tests_db[name]={
                "full_name": u["new_test"]["full_name"],
                "description": u["new_test"]["description"],
                "normal_range": u["new_test"]["normal_range"],
                "image": u["new_test"]["image"]
            }
            cat = u["new_test"]["category"]
            if name not in CATEGORIES[cat]["tests"]:
                CATEGORIES[cat]["tests"].append(name)
            save_db(tests_db, TESTS_PATH)
            u["adding_step"]=None
            u["new_test"]={}
            await context.bot.send_message(chat_id,f"✅ تم إضافة التحليل {name} تحت {cat}")
            return

    # ---- عرض تحليل ----
    if u.get("awaiting_test"):
        test_name = u["awaiting_test"]
        data = tests_db.get(test_name)
        if not data:
            await context.bot.send_message(chat_id,"❌ لا يوجد هذا التحليل.")
            u["awaiting_test"]=None
            return
        msg = f"🔹 التحليل: {data['full_name']}\n💡 الوصف: {data['description']}\n📊 النطاق الطبيعي:\n"
        for k,v in data["normal_range"].items():
            emoji = {"male":"👨 ذكر","female":"👩 أنثى","children":"🧒 أطفال","newborn":"👶 حديث الولادة","elderly":"👵 كبار السن"}.get(k,k)
            msg+=f"{emoji}: {v}\n"
        if data.get("image"):
            try:
                await context.bot.send_photo(chat_id, photo=open(data["image"],"rb"), caption=msg)
            except:
                await context.bot.send_message(chat_id,msg)
        else:
            await context.bot.send_message(chat_id,msg)
        u["awaiting_test"]=None
        return

# ========== التعامل مع الأزرار ==========
async def handle_callback(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data
    u = get_user(chat_id)

    if data=="home":
        await query.answer()
        await query.edit_message_text("اختر التصنيف:", reply_markup=kb_category_root())
        return
    if data.startswith("cat:"):
        _,cat = data.split(":")
        await query.answer()
        await query.edit_message_text(f"{CATEGORIES[cat]['title']} — اختر التحليل:", reply_markup=kb_tests_for(cat))
        return
    if data.startswith("test:"):
        _,test = data.split(":")
        u["awaiting_test"]=test
        await query.answer()
        await context.bot.send_message(chat_id,"🔹 التحليل محدد. اضغط /start لإظهار التفاصيل.")
        return

# ========== تشغيل البوت ==========
if __name__=="__main__":
    BOT_TOKEN = "8402805384:AAG-JnszBhh8GMDIvf1oeKNUvXi07MOXSWo"  #    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtest", add_test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()
