import random
import datetime
import os
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardRemove, CallbackQuery
)
import database as db
from ai_service import get_ai_fitness_response  # AI ni chaqiramiz

user_router = Router()

# ==========================================================
#                 1. USER HOLATLARI (FSM)
# ==========================================================
class UserState(StatesGroup):
    reg_name = State()
    reg_phone = State()
    reg_age = State()
    reg_weight = State()
    
    reading_manual = State()
    watching_intro = State()
    solving_quiz = State()
    
    selecting_course = State()  
    confirming_course = State() 
    
    dashboard = State()         
    reporting_in = State()      
    reporting_out = State()     
    waiting_next_day = State()  

# ==========================================================
#                 2. KLAVIATURALAR (UI)
# ==========================================================

def kb_contact():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]], 
        resize_keyboard=True
    )

def kb_manual_next():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Tanishib chiqdim, Videoga o'tish ➡️")]], 
        resize_keyboard=True
    )

def kb_start_quiz():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🧠 Testni Boshlash", callback_data="start_quiz")]]
    )

def kb_courses():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 D-ToxFit"), KeyboardButton(text="🔴 Torpedo")]
        ], 
        resize_keyboard=True
    )

# --- MUKAMMALLASHTIRILGAN USER PANELI ---
def kb_dashboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏋️‍♂️ Bugungi Mashq")],
            [KeyboardButton(text="📊 Kunlik Hisobot"), KeyboardButton(text="🤖 AI Maslahatchi")],
            [KeyboardButton(text="👤 Profilim")]
        ], 
        resize_keyboard=True,
        input_field_placeholder="Quyidagilardan birini tanlang ⬇️"
    )

def kb_walk_check():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha, yurdim", callback_data="walk_yes"),
             InlineKeyboardButton(text="❌ Yo'q hali", callback_data="walk_no")]
        ]
    )

# ==========================================================
#                 3. START & STATUS CHECK
# ==========================================================

@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer(
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "Fitnes botimizga xush kelibsiz! Maqsad sari birga yuramiz.\n"
            "Avval ro'yxatdan o'tib olaylik.\n\n"
            "✍️ <i>Iltimos, Ism va Familiyangizni kiriting:</i>", 
            parse_mode="HTML"
        )
        await state.set_state(UserState.reg_name)
        return

    if user['status'] == 'PENDING_APPROVAL':
        await message.answer(
            f"⏳ <b>Arizangiz ko'rib chiqilmoqda.</b>\n\n"
            f"👤 Ism: {user['full_name']}\n"
            f"🆔 ID: <code>{user['six_digit_id']}</code>\n\n"
            "<i>Tez orada admin tasdiqlaydi. Kuting...</i>", 
            parse_mode="HTML"
        )
        return

    if user['status'] == 'REJECTED':
        await message.answer("🚫 <b>Kechirasiz, sizning arizangiz rad etilgan yoki profilingiz bloklangan.</b>", parse_mode="HTML")
        return

    if user['status'] == 'FINISHED':
        await message.answer(
            "🏆 <b>TABRIKLAYMIZ! SIZ KURSNI TUGATDINGIZ!</b>\n\n"
            "Siz ajoyib natija ko'rsatdingiz. Yangi marralar sari olg'a!\n"
            "<i>Yangi kurs olish uchun admin bilan bog'laning.</i>", 
            parse_mode="HTML"
        )
        return

    if user['status'] == 'ACTIVE' and not user['current_course']:
        manual_link = await db.get_manual_link() or "https://t.me/"
        await message.answer(
            f"🎉 <b>Tabriklaymiz, {user['full_name']}!</b>\n\n"
            f"Siz muvaffaqiyatli tasdiqlandingiz.\n"
            f"Kursni boshlashdan oldin <b>Qo'llanma</b> bilan tanishib chiqing:\n\n"
            f"👉 <a href='{manual_link}'>QO'LLANMANI O'QISH</a>",
            reply_markup=kb_manual_next(), 
            parse_mode="HTML", 
            disable_web_page_preview=False
        )
        await state.set_state(UserState.reading_manual)
        return

    if user['status'] == 'ACTIVE' and user['current_course']:
        current_state = await state.get_state()
        if current_state == UserState.waiting_next_day:
             await message.answer(
                 "🌙 <b>Bugungi rejani bajardingiz!</b>\n\n"
                 "Ertangi mashqlar soat <b>07:00</b> da ochiladi.\n"
                 "Yaxshi dam oling!", 
                 reply_markup=kb_dashboard(), 
                 parse_mode="HTML"
             )
        else:
            course_name = "D-ToxFit" if user['current_course'] == "PREMIUM" else "Torpedo"
            await message.answer(
                f"🔥 <b>{course_name} — {user['current_day']}-KUN</b>\n\n"
                "Asosiy menyudasiz. Nima qilamiz?", 
                reply_markup=kb_dashboard(), 
                parse_mode="HTML"
            )
            await state.set_state(UserState.dashboard)

# ==========================================================
#                 4. REGISTRATSIYA
# ==========================================================

@user_router.message(UserState.reg_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 <b>Telefon raqamingizni yuboring:</b>\n(Pastdagi tugmani bosing)", reply_markup=kb_contact(), parse_mode="HTML")
    await state.set_state(UserState.reg_phone)

@user_router.message(UserState.reg_phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("🔢 <b>Yoshingizni kiriting (faqat raqam):</b>", reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    await state.set_state(UserState.reg_age)

@user_router.message(UserState.reg_age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("⚠️ Iltimos, faqat raqam yozing.")
    await state.update_data(age=int(message.text))
    await message.answer("⚖️ <b>Vazningizni kiriting (kg):</b>\nMasalan: 70.5", parse_mode="HTML")
    await state.set_state(UserState.reg_weight)

@user_router.message(UserState.reg_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try: weight = float(message.text.replace(",", "."))
    except: return await message.answer("⚠️ Format noto'g'ri. Masalan: 75 yoki 75.5")
    
    data = await state.get_data()
    six_digit_id = random.randint(100000, 999999) 
    await db.add_user(message.from_user.id, data['name'], data['phone'], data['age'], weight, six_digit_id)
    await state.clear()
    
    await message.answer(
        f"✅ <b>Arizangiz qabul qilindi!</b>\n\n"
        f"👤 Ism: {data['name']}\n"
        f"🆔 ID: <code>{six_digit_id}</code>\n\n"
        "<i>Admin tasdiqlashini kuting...</i>", 
        parse_mode="HTML"
    )

# ==========================================================
#                 5. LMS (VIDEO & TEST)
# ==========================================================

@user_router.message(UserState.reading_manual, F.text.contains("Videoga"))
async def show_intro_video(message: types.Message, state: FSMContext, bot: Bot):
    intro = await db.get_intro()
    
    if not intro:
        await message.answer("✅ Kirish qismi o'tkazib yuborildi (Admin video yuklamagan).")
        await message.answer("👇 <b>Quyidagi kurslardan birini tanlang:</b>", reply_markup=kb_courses(), parse_mode="HTML")
        await state.set_state(UserState.selecting_course)
        return

    await message.answer("🎬 <b>KIRISH VIDEO DARSLIK</b>\n\n<i>Videoni diqqat bilan ko'ring, so'ngra test savollari bo'ladi!</i>", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    
    try:
        await bot.send_video(
            chat_id=message.chat.id,
            video=intro['file_id'],
            caption=intro['caption'],
            reply_markup=kb_start_quiz()
        )
    except:
        await message.answer("⚠️ Videoni yuklashda xatolik yuz berdi.", reply_markup=kb_start_quiz())
    
    await state.set_state(UserState.watching_intro)

@user_router.callback_query(F.data == "start_quiz")
async def start_quiz_handler(call: CallbackQuery, state: FSMContext):
    quizzes = await db.get_all_quizzes()
    if not quizzes:
        await call.message.delete()
        await call.message.answer("✅ Savollar mavjud emas. Kursni tanlang:", reply_markup=kb_courses())
        await state.set_state(UserState.selecting_course)
        return

    await state.update_data(quiz_index=0, score=0, total_q=len(quizzes))
    await send_quiz_question(call.message, 0, quizzes, state)
    await state.set_state(UserState.solving_quiz)

async def send_quiz_question(message, index, quizzes, state):
    q_data = quizzes[index]
    question = q_data['question']
    options = q_data['options'].split("|")
    
    kb_rows = []
    for i, opt in enumerate(options):
        kb_rows.append([InlineKeyboardButton(text=opt, callback_data=f"answer_{i}")])
    
    await message.answer(
        f"❓ <b>{index + 1}-SAVOL:</b>\n\n{question}", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode="HTML"
    )

@user_router.callback_query(UserState.solving_quiz, F.data.startswith("answer_"))
async def check_answer(call: CallbackQuery, state: FSMContext):
    user_answer = int(call.data.split("_")[1])
    data = await state.get_data()
    idx = data['quiz_index']
    quizzes = await db.get_all_quizzes()
    
    correct_idx = quizzes[idx]['correct_index']
    score = data['score']
    
    if user_answer == correct_idx:
        score += 1
        res_text = "✅ <b>To'g'ri!</b>"
    else:
        res_text = "❌ <b>Noto'g'ri!</b>"
    
    await call.message.delete()
    await call.message.answer(res_text, parse_mode="HTML")
    
    next_idx = idx + 1
    if next_idx < len(quizzes):
        await state.update_data(quiz_index=next_idx, score=score)
        await send_quiz_question(call.message, next_idx, quizzes, state)
    else:
        percentage = (score / len(quizzes)) * 100
        if percentage >= 50:
            await call.message.answer(
                f"🎉 <b>Tabriklaymiz!</b>\nSiz {percentage:.0f}% natija bilan sinovdan o'tdingiz.\n\n👇 <b>Endi kursni tanlashingiz mumkin:</b>",
                reply_markup=kb_courses(),
                parse_mode="HTML"
            )
            await state.set_state(UserState.selecting_course)
        else:
            await call.message.answer(
                f"😕 <b>Afsuski, natijangiz {percentage:.0f}%.</b>\nKamida 50% to'plashingiz kerak edi.\n\n<i>Qayta urinib ko'ring:</i>",
                reply_markup=kb_start_quiz(),
                parse_mode="HTML"
            )

# ==========================================================
#                 6. KURS TANLASH
# ==========================================================

@user_router.message(UserState.selecting_course, F.text.in_(["🟢 D-ToxFit", "🔴 Torpedo"]))
async def select_course_handler(message: types.Message, state: FSMContext):
    selected_text = message.text
    if "D-ToxFit" in selected_text: course_code = "PREMIUM"
    else: course_code = "TORPEDO"
    
    await state.update_data(course_code=course_code, course_name=selected_text)
    
    await message.answer(
        f"🎯 <b>Tanlangan kurs: {selected_text}</b>\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ HA, BOSHLAYMIZ", callback_data="confirm_start")],
            [InlineKeyboardButton(text="🔙 ORTGA", callback_data="back_select")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(UserState.confirming_course)

@user_router.callback_query(UserState.confirming_course)
async def confirm_course_callback(call: types.CallbackQuery, state: FSMContext):
    if call.data == "back_select":
        await call.message.delete()
        await call.message.answer("Kursni qaytadan tanlang:", reply_markup=kb_courses())
        await state.set_state(UserState.selecting_course)
        return

    if call.data == "confirm_start":
        data = await state.get_data()
        await db.start_user_course(call.from_user.id, data['course_code'])
        await call.message.delete()
        await call.message.answer(
            f"🚀 <b>{data['course_name']} boshlandi!</b>\n\n"
            "Sizga omad tilaymiz! Asosiy menyudan kerakli bo'limni tanlang.",
            reply_markup=kb_dashboard(), 
            parse_mode="HTML"
        )
        await state.set_state(UserState.dashboard)

# ==========================================================
#                 7. ASOSIY MENYU TUGMALARI (DASHBOARD)
# ==========================================================

# 1. BUGUNGI MASHQ
@user_router.message(F.text == "🏋️‍♂️ Bugungi Mashq")
async def get_task(message: types.Message, bot: Bot):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'ACTIVE' or not user['current_course']: return

    if user['report_submitted_today']:
        await message.answer("✅ <b>Bugungi vazifa bajarilgan.</b>\nErtangi kunni kuting!", parse_mode="HTML")
        return

    raw_content = await db.get_day_content_list(user['current_course'], user['current_day'])
    if not raw_content:
        await message.answer("⚠️ <i>Mashqlar hali yuklanmagan yoki kurs yakunlangan.</i>", parse_mode="HTML")
        return

    priority_map = {'video': 1, 'photo': 2, 'voice': 3, 'document': 3, 'text': 4}
    content_list = [dict(item) for item in raw_content]
    content_list.sort(key=lambda x: priority_map.get(x['content_type'], 5))

    channel = os.getenv(f"{user['current_course']}_CHANNEL")
    if not channel: return await message.answer("❌ Tizim xatoligi: Kanal topilmadi.")

    await message.answer(f"📅 <b>{user['current_day']}-KUN MASHG'ULOTLARI:</b>", parse_mode="HTML")

    for item in content_list:
        try:
            await bot.copy_message(chat_id=message.from_user.id, from_chat_id=channel, message_id=int(item['file_id']), parse_mode="HTML")
        except:
            pass 

    await message.answer("Mashqlarni bajarib bo'lgach, <b>'📊 Kunlik Hisobot'</b> tugmasini bosing.", parse_mode="HTML")

# 2. PROFILIM
@user_router.message(F.text == "👤 Profilim")
async def show_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user: return
    
    course_n = "D-ToxFit 🟢" if user['current_course'] == 'PREMIUM' else "Torpedo 🔴" if user['current_course'] == 'TORPEDO' else "Tanlanmagan"
    
    text = (
        f"👤 <b>Shaxsiy Profilingiz:</b>\n\n"
        f"📛 <b>Ism:</b> {user['full_name']}\n"
        f"🆔 <b>ID:</b> <code>{user['six_digit_id']}</code>\n"
        f"⚖️ <b>Boshlang'ich vazn:</b> {user['weight']} kg\n\n"
        f"📚 <b>Joriy kurs:</b> {course_n}\n"
        f"📅 <b>Bosqich:</b> {user['current_day']}-kun"
    )
    await message.answer(text, parse_mode="HTML")

# 3. AI MASLAHATCHI (MOTIVATSIYA VA KALORIYA)
@user_router.message(F.text == "🤖 AI Maslahatchi")
async def ai_advisor_btn(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'ACTIVE': return

    quotes = [
        "Sizning eng katta raqibingiz — bu kechagi o'zingiz. Bugun undan kuchliroq bo'ling! 💪",
        "Muvaffaqiyat kichik, ammo har kuni takrorlanadigan qadamlardan iborat. Aslo to'xtamang! 🚶‍♂️",
        "Sog'lom tana — sog'lom aql. O'zingizga bo'lgan ishonchni bugundan yarating! ✨",
        "Qiyin bo'lishi mumkin, lekin bu imkonsiz degani emas. Maqsad sari olg'a! 🎯",
        "Natija darhol ko'rinmasligi mumkin, lekin har bir harakatingiz sizni maqsadga yaqinlashtirmoqda. 📈"
    ]
    
    quote = random.choice(quotes)
    
    text = (
        f"💡 <i>\"{quote}\"</i>\n\n"
        f"🤖 <b>Salom {user['full_name']}! Men sizning shaxsiy AI maslahatchingizman.</b>\n\n"
        f"🍽 Bugun nimalar tanovul qildingiz? Yegan ovqatlaringizni yozib yuborsangiz, ularning <b>kaloriyasini hisoblab berishim</b> mumkin.\n\n"
        f"Yoki ozish, mashqlar va sog'lom ovqatlanish bo'yicha qanday savolingiz bor? Bemalol yozing!"
    )
    
    await message.answer(text, parse_mode="HTML")

# --- YURISH JAVOBLARI ---
@user_router.callback_query(F.data == "walk_yes")
async def walk_yes_handler(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer("🔥 <b>Ofarin!</b>\n\nSizdagi intizomga havas qilsa arziydi. Qon aylanishi yaxshilandi, kayfiyat ko'tarildi.\nAynan shunday davom etamiz! 🚀", parse_mode="HTML")

@user_router.callback_query(F.data == "walk_no")
async def walk_no_handler(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer("🚶‍♂️ <b>Hali kech emas!</b>\n\n30 daqiqa yurish — bu salomatlik uchun eng oson va foydali sarmoya.\nHoziroq o'rningizdan turib, biroz harakat qiling. Tanangiz sizga rahmat aytadi! 💪", parse_mode="HTML")

# ==========================================================
#                 8. HISOBOT VA LOGIKA
# ==========================================================

@user_router.message(F.text == "📊 Kunlik Hisobot")
async def start_report(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'ACTIVE' or not user['current_course']: return
    if user['report_submitted_today']:
        return await message.answer("✅ Siz bugungi hisobotni topshirib bo'lgansiz.", parse_mode="HTML")

    await message.answer("🍽 <b>Hisobot vaqti!</b>\n\nBugun jami qancha kaloriya qabul qildingiz? (Faqat raqam yozing):", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(UserState.reporting_in)

@user_router.message(UserState.reporting_in)
async def report_cal_in(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("⚠️ Iltimos, faqat raqam kiriting.")
    await state.update_data(cal_in=int(message.text))
    await message.answer("🔥 Qancha kaloriya yo'qotdingiz? (Faqat raqam):", parse_mode="HTML")
    await state.set_state(UserState.reporting_out)

@user_router.message(UserState.reporting_out)
async def report_cal_out(message: types.Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit(): return await message.answer("⚠️ Faqat raqam kiriting.")
    
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    
    await db.save_report(message.from_user.id, user['current_course'], user['current_day'], data['cal_in'], int(message.text))
    await state.clear()

    start_date = datetime.datetime.strptime(user['start_date'], "%Y-%m-%d").date() if user['start_date'] else datetime.date.today()
    today = datetime.date.today()
    days_since_start = (today - start_date).days + 1
    
    if datetime.datetime.now().hour < 7: days_since_start -= 1

    next_day = user['current_day'] + 1
    next_day_content = await db.get_day_content_list(user['current_course'], next_day)

    if not next_day_content and user['current_day'] >= 10:
        await db.update_user_status(user['user_id'], "FINISHED")
        await message.answer(
            "🎉 <b>TABRIKLAYMIZ! KURS MUVAFFAQIYATLI YAKUNLANDI!</b> 🏆\n\n"
            "Siz barcha bosqichlardan o'tdingiz. Natijani saqlab qolishda davom eting!",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if user['current_day'] < days_since_start and next_day_content:
        await db.increment_user_day(user['user_id'])
        priority_map = {'video': 1, 'photo': 2, 'voice': 3, 'document': 3, 'text': 4}
        content_list = sorted([dict(item) for item in next_day_content], key=lambda x: priority_map.get(x['content_type'], 5))
        channel = os.getenv(f"{user['current_course']}_CHANNEL")

        await message.answer(
            f"✅ <b>HISOBOT QABUL QILINDI!</b>\n\n"
            f"Sizda qarz darslar borligi uchun, <b>{next_day}-KUN</b> mashg'ulotini hoziroq taqdim etamiz! 🔥",
            parse_mode="HTML", reply_markup=kb_dashboard()
        )

        for item in content_list:
            try: await bot.copy_message(message.from_user.id, channel, int(item['file_id']), parse_mode="HTML")
            except: pass
            
        await state.set_state(UserState.dashboard)

    else:
        await message.answer(
            "✅ <b>HISOBOT QABUL QILINDI!</b>\n\n"
            "Siz ajoyib natija ko'rsatdingiz!\n"
            "Ertangi mashqlar soat <b>07:00 da</b> ochiladi.\n"
            "Yaxshi dam oling! 😴",
            parse_mode="HTML", reply_markup=kb_dashboard()
        )
        await state.set_state(UserState.waiting_next_day)

@user_router.message(UserState.waiting_next_day)
async def waiting_handler(message: types.Message):
    # Agar shu holatda menyu tugmasi bosilsa, pastdagi F.text handlerlar ushlab olishi uchun pass qildik
    if message.text in ["🏋️‍♂️ Bugungi Mashq", "📊 Kunlik Hisobot", "🤖 AI Maslahatchi", "👤 Profilim"]:
        return
    await message.answer("💤 <b>Bot dam olmoqda...</b>\nErtangi mashqlar soat 07:00 da yuboriladi.\nLekin AI maslahatchiga savol berishingiz mumkin!", parse_mode="HTML")


# ==========================================================
#                 9. AI BILAN ERKIN SUHBAT
# ==========================================================

@user_router.message(F.text)
async def ai_chat_handler(message: types.Message, state: FSMContext, bot: Bot):
    user_text = message.text

    # Tizim tugmalari noto'g'ri ishlamasligi uchun xavfsizlik
    if user_text in ["🏋️‍♂️ Bugungi Mashq", "📊 Kunlik Hisobot", "🤖 AI Maslahatchi", "👤 Profilim"]:
        return

    # Foydalanuvchi muhim ro'yxatdan o'tish yoki hisobot berish jarayonida bo'lsa AI jim turadi
    current_state = await state.get_state()
    if current_state in [
        UserState.reg_name, UserState.reg_phone, UserState.reg_age, UserState.reg_weight, 
        UserState.solving_quiz, UserState.reporting_in, UserState.reporting_out
    ]:
        return

    # Userni tekshirish
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'ACTIVE' or not user['current_course']:
        return

    # AI javob berish jarayoni
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        reply = await get_ai_fitness_response(user_text)

        # Uzun matnlarni bo'lib yuborish
        if len(reply) > 4000:
            for i in range(0, len(reply), 4000):
                await message.answer(reply[i:i+4000], parse_mode="HTML")
        else:
            await message.answer(reply, parse_mode="HTML")
            
    except Exception as e:
        await message.answer("⚠️ Texnik uzilish yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring.")
