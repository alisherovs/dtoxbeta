import os
import math
import pandas as pd
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, CallbackQuery
)
from dotenv import load_dotenv
import database as db

# .env faylini chaqiramiz (agar main.py da chaqirilmagan bo'lsa, xavfsizlik uchun)
load_dotenv()

admin_router = Router()

# ==========================================================
#     ADMIN XAVFSIZLIK FILTRI (Mukammal versiya)
# ==========================================================
# .env dagi ADMIN_ID ni o'qiymiz (Masalan: "8008006509, 8008157657")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "")

# Vergul bilan ajratilgan raqamlarni tozalab, ro'yxatga (list) aylantiramiz
ADMIN_IDS = [int(i.strip()) for i in ADMIN_ID_RAW.split(",") if i.strip().isdigit()]

# Ushbu routerdagi barcha message va callbacklar FAQAT shu ro'yxatdagi adminlarga ishlaydi!
admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

# --- 1. STATES (HOLATLAR) ---
class AdminState(StatesGroup):
    search_user = State()
    manual_update = State()

    # Kurs va Kontent
    content_course = State()
    setting_course_days = State()
    content_view_day = State()
    uploading_media = State()

    # Intro va Test (LMS)
    intro_upload = State()
    quiz_question = State()
    quiz_options = State()
    quiz_correct = State()

    # Broadcast (Xabar yuborish)
    broadcast_type = State()
    broadcast_msg = State()

# --- 2. KLAVIATURALAR (UI) ---

def admin_home_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🆕 Yangi Zayavkalar"), KeyboardButton(text="🔍 Qidiruv")],
        [KeyboardButton(text="📚 Kurs Kontenti"), KeyboardButton(text="🎬 Kirish va Testlar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Xabar Yuborish")],
        [KeyboardButton(text="📖 Qo'llanma")]
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Asosiy Menyu")]],
        resize_keyboard=True
    )

def finish_upload_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ TUGATISH")],
        [KeyboardButton(text="🔙 Bekor qilish")]
    ], resize_keyboard=True)

# Intro va Test Menyusi
def intro_test_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📹 Intro Videoni Yuklash", callback_data="upload_intro")],
        [InlineKeyboardButton(text="➕ Yangi Savol Qo'shish", callback_data="add_quiz")],
        [InlineKeyboardButton(text="📋 Savollar Ro'yxati (O'chirish)", callback_data="list_quiz")]
    ])

# Dinamik Kunlar Gridi
def days_grid_kb(course_code, total_days):
    buttons = []
    row = []
    for i in range(1, total_days + 1):
        row.append(InlineKeyboardButton(text=f"{i}", callback_data=f"day_{course_code}_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⚙️ Kunlar sonini o'zgartirish", callback_data=f"resetdays_{course_code}")])
    buttons.append([InlineKeyboardButton(text="🔙 Kurslarga qaytish", callback_data="back_to_courses")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def day_actions_kb(course, day):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"view_{course}_{day}"),
         InlineKeyboardButton(text="🗑 Tozalash", callback_data=f"clear_{course}_{day}")],
        [InlineKeyboardButton(text="➕ Media Qo'shish", callback_data=f"add_{course}_{day}")],
        [InlineKeyboardButton(text="🔙 Kunlarga qaytish", callback_data=f"back_to_days_{course}")]
    ])

# --- 3. ASOSIY START ---

@admin_router.message(Command(commands=["start", "admin"]))
async def admin_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👨‍💼 <b>Admin Panel</b>\nXush kelibsiz, Admin! Barcha bo'limlar ishga tayyor.",
        reply_markup=admin_home_kb(),
        parse_mode="HTML"
    )

@admin_router.message(F.text == "🔙 Asosiy Menyu")
async def back_to_home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu:", reply_markup=admin_home_kb())

# ==========================================================
#              4. ZAYAVKALAR (CARD STYLE + PAGINATION)
# ==========================================================

@admin_router.message(F.text == "🆕 Yangi Zayavkalar")
async def view_users_start(message: types.Message):
    await show_users_page(message, page=1)

async def show_users_page(message_or_call, page):
    limit = 3  # Bir sahifada 3 ta user
    users, total = await db.get_pending_users_paginated(page, limit)

    is_message = isinstance(message_or_call, types.Message)

    if not users:
        text = "✅ <b>Ajoyib! Yangi arizalar mavjud emas.</b>\nBarcha so'rovlar ko'rib chiqilgan."
        if is_message:
            await message_or_call.answer(text, parse_mode="HTML")
        else:
            try:
                await message_or_call.message.edit_text(text, parse_mode="HTML")
            except Exception:
                try:
                    await message_or_call.message.delete()
                except Exception:
                    pass
                await message_or_call.message.answer(text, parse_mode="HTML")
        return

    total_pages = math.ceil(total / limit)
    text = f"🆕 <b>KUTILAYOTGAN ARIZALAR</b>\n"
    text += f"📄 Sahifa: <b>{page}/{total_pages}</b> | Jami: <b>{total}</b> ta\n\n"

    kb_rows = []
    for u in users:
        text += f"👤 <b>{u['full_name']}</b>\n"
        text += f"📞 Tel: {u['phone']}\n"
        text += f"📊 Yosh: {u['age']} | ⚖️ Vazn: {u['weight']} kg\n"
        text += f"🆔 ID: <code>{u['six_digit_id']}</code>\n"
        text += "➖➖➖➖➖➖➖➖➖➖\n"

        kb_rows.append([
            InlineKeyboardButton(text=f"✅ Tasdiqlash ({u['six_digit_id']})", callback_data=f"approve_{u['user_id']}"),
            InlineKeyboardButton(text=f"❌ Rad etish", callback_data=f"reject_{u['user_id']}")
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"users_page_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"users_page_{page+1}"))

    if nav_row:
        kb_rows.append(nav_row)

    kb_rows.append([InlineKeyboardButton(text="🚫 Yopish", callback_data="close_users_list")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if is_message:
        await message_or_call.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        try:
            await message_or_call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await message_or_call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("users_page_"))
async def users_pagination(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    await call.answer()
    await show_users_page(call, page)

@admin_router.callback_query(F.data == "close_users_list")
async def close_list(call: CallbackQuery):
    await call.answer()
    await call.message.delete()

@admin_router.callback_query(F.data.startswith(("approve_", "reject_")))
async def process_decision(call: CallbackQuery, bot: Bot):
    action, uid = call.data.split("_")
    user_id = int(uid)
    user_info = await db.get_user(user_id)
    name = user_info['full_name'] if user_info else "Foydalanuvchi"

    if action == "approve":
        await db.update_user_status(user_id, "ACTIVE")
        status_msg = f"✅ {name} tasdiqlandi!"
        try:
            await bot.send_message(
                user_id,
                "🎉 <b>Tabriklaymiz! Arizangiz qabul qilindi.</b>\n/start bosib davom eting.",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await db.update_user_status(user_id, "REJECTED")
        status_msg = f"❌ {name} rad etildi."
        try:
            await bot.send_message(user_id, "🚫 <b>Arizangiz rad etildi.</b>", parse_mode="HTML")
        except Exception:
            pass

    await call.answer(status_msg, show_alert=True)
    await show_users_page(call, 1)

# ==========================================================
#              5. INTRO VIDEO VA TESTLAR (LMS)
# ==========================================================

@admin_router.message(F.text == "🎬 Kirish va Testlar")
async def intro_test_menu(message: types.Message):
    intro = await db.get_intro()
    status = "✅ Yuklangan" if intro else "❌ Yuklanmagan"
    quizzes = await db.get_all_quizzes()

    text = (
        f"🎬 <b>KIRISH QISMI SOZLAMALARI</b>\n\n"
        f"📹 <b>Intro Video:</b> {status}\n"
        f"❓ <b>Savollar soni:</b> {len(quizzes)} ta\n\n"
        "<i>User qo'llanmani o'qigach, shu video ko'rsatiladi va keyin savollar beriladi.</i>"
    )
    await message.answer(text, reply_markup=intro_test_kb(), parse_mode="HTML")

@admin_router.callback_query(F.data == "upload_intro")
async def ask_intro(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("📹 <b>Intro videoni yuboring:</b>", reply_markup=back_kb(), parse_mode="HTML")
    await state.set_state(AdminState.intro_upload)

@admin_router.message(AdminState.intro_upload, F.video)
async def save_intro_handler(message: types.Message, state: FSMContext):
    await db.save_intro(message.video.file_id, message.caption or "Intro")
    await message.answer("✅ <b>Intro video saqlandi!</b>", reply_markup=admin_home_kb(), parse_mode="HTML")
    await state.clear()

@admin_router.message(AdminState.intro_upload)
async def invalid_intro_handler(message: types.Message):
    if message.text == "🔙 Asosiy Menyu":
        return
    await message.answer("⚠️ Iltimos, aynan video yuboring yoki '🔙 Asosiy Menyu' tugmasini bosing.")

@admin_router.callback_query(F.data == "add_quiz")
async def ask_question(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("❓ <b>Savol matnini yozing:</b>", parse_mode="HTML")
    await state.set_state(AdminState.quiz_question)

@admin_router.message(AdminState.quiz_question)
async def ask_options(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    await message.answer(
        "🔠 <b>Variantlarni vergul bilan ajratib yozing:</b>\n<i>Masalan: Ha, Yo'q, Bilmayman</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.quiz_options)

@admin_router.message(AdminState.quiz_options)
async def ask_correct(message: types.Message, state: FSMContext):
    options = [opt.strip() for opt in message.text.split(",") if opt.strip()]
    if len(options) < 2:
        return await message.answer("⚠️ Kamida 2 ta variant yozing.")

    await state.update_data(options=options)

    kb = []
    for idx, opt in enumerate(options):
        kb.append([InlineKeyboardButton(text=opt, callback_data=f"correct_{idx}")])

    await message.answer(
        "✅ <b>To'g'ri javobni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.quiz_correct)

@admin_router.callback_query(AdminState.quiz_correct, F.data.startswith("correct_"))
async def save_quiz_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.add_quiz(data['question'], data['options'], int(call.data.split("_")[1]))
    await call.answer("Savol saqlandi")
    await call.message.edit_text("✅ <b>Savol saqlandi!</b>", parse_mode="HTML")
    await state.clear()
    await intro_test_menu(call.message)

@admin_router.callback_query(F.data == "list_quiz")
async def list_quizzes(call: CallbackQuery):
    quizzes = await db.get_all_quizzes()
    await call.answer()
    if not quizzes:
        return await call.message.answer("❌ Savollar yo'q.")

    kb = []
    for q in quizzes:
        question_preview = q['question'][:20] + "..." if len(q['question']) > 20 else q['question']
        kb.append([InlineKeyboardButton(text=f"🗑 {question_preview}", callback_data=f"delquiz_{q['id']}")])

    kb.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_intro")])
    await call.message.edit_text(
        "📋 <b>Savollar ro'yxati:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data.startswith("delquiz_"))
async def delete_quiz_handler(call: CallbackQuery):
    await db.delete_quiz(int(call.data.split("_")[1]))
    await call.answer("O'chirildi")
    await list_quizzes(call)

@admin_router.callback_query(F.data == "back_to_intro")
async def back_intro_handler(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await intro_test_menu(call.message)

# ==========================================================
#              6. KURS KONTENTI (D-ToxFit & TORPEDO)
# ==========================================================

@admin_router.message(F.text == "📚 Kurs Kontenti")
async def content_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 D-ToxFit", callback_data="course_PREMIUM")],
        [InlineKeyboardButton(text="🔴 Torpedo", callback_data="course_TORPEDO")]
    ])
    await message.answer("📂 <b>Qaysi kursni tahrirlaymiz?</b>", reply_markup=kb, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("course_"))
async def select_course_process(call: CallbackQuery, state: FSMContext):
    await call.answer()
    course_code = call.data.split("_")[1]
    days = await db.get_course_days(course_code)

    if not days:
        await state.update_data(course_code=course_code)
        await call.message.edit_text(
            f"⚙️ <b>{course_code}</b> uchun kunlar soni belgilanmagan.\n"
            "Bu kurs necha kundan iborat? (Raqam yozing)",
            parse_mode="HTML"
        )
        await state.set_state(AdminState.setting_course_days)
    else:
        await call.message.edit_text(
            f"🗓 <b>{course_code}</b> ({days} kun). Kunni tanlang:",
            reply_markup=days_grid_kb(course_code, days),
            parse_mode="HTML"
        )

@admin_router.message(AdminState.setting_course_days)
async def save_course_days_handler(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Faqat raqam yozing.")

    days = int(message.text)
    if days <= 0:
        return await message.answer("⚠️ Kunlar soni 1 yoki undan katta bo'lishi kerak.")

    data = await state.get_data()
    await db.set_course_days(data['course_code'], days)
    await message.answer(
        f"✅ <b>{data['course_code']}</b>: {days} kun belgilandi.",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await message.answer(
        f"🗓 <b>{data['course_code']}</b> kursi.",
        reply_markup=days_grid_kb(data['course_code'], days),
        parse_mode="HTML"
    )
    await state.clear()

@admin_router.callback_query(F.data.startswith("resetdays_"))
async def reset_days(call: CallbackQuery, state: FSMContext):
    await call.answer()
    c = call.data.split("_")[1]
    await state.update_data(course_code=c)
    await call.message.edit_text(f"⚙️ <b>{c}</b>: Yangi kunlar sonini yozing:", parse_mode="HTML")
    await state.set_state(AdminState.setting_course_days)

@admin_router.callback_query(F.data == "back_to_courses")
async def back_course(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await content_start(call.message)

@admin_router.callback_query(F.data.startswith("back_to_days_"))
async def back_days(call: CallbackQuery):
    await call.answer()
    c = call.data.split("_")[3]
    d = await db.get_course_days(c)
    await call.message.edit_text(
        f"🗓 <b>{c}</b> kursi.",
        reply_markup=days_grid_kb(c, d),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data.startswith("day_"))
async def day_menu(call: CallbackQuery):
    await call.answer()
    _, c, d = call.data.split("_")
    items = await db.get_day_content_list(c, d)
    await call.message.edit_text(
        f"⚙️ <b>{c} {d}-kun</b>\n📂 Fayllar: {len(items)} ta",
        reply_markup=day_actions_kb(c, d),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data.startswith("view_"))
async def view_c(call: CallbackQuery, bot: Bot):
    await call.answer()
    _, c, d = call.data.split("_")
    items = await db.get_day_content_list(c, d)
    chan = os.getenv(f"{c}_CHANNEL")

    if not items:
        return await call.answer("Bo'sh!", show_alert=True)

    await call.message.answer(f"👁 <b>{c} {d}-kun</b>:", parse_mode="HTML")
    for i in items:
        try:
            await bot.copy_message(call.from_user.id, chan, int(i['file_id']))
        except Exception:
            pass

@admin_router.callback_query(F.data.startswith("clear_"))
async def clear_c(call: CallbackQuery):
    await call.answer()
    _, c, d = call.data.split("_")
    await db.delete_day_content(c, d)
    await call.answer("Tozalandi", show_alert=True)
    await day_menu(call)

@admin_router.callback_query(F.data.startswith("add_"))
async def add_c(call: CallbackQuery, state: FSMContext):
    await call.answer()
    _, c, d = call.data.split("_")
    await state.update_data(c=c, d=d)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(
        f"📥 <b>{c} {d}-kun</b>. Media yuboring.\nTugatgach '✅ TUGATISH' bosing.",
        reply_markup=finish_upload_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.uploading_media)

@admin_router.message(AdminState.uploading_media)
async def upload_loop(message: types.Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi", reply_markup=admin_home_kb())
        return

    if message.text == "✅ TUGATISH":
        await state.clear()
        await message.answer("✅ Saqlandi.", reply_markup=admin_home_kb())
        return

    data = await state.get_data()
    chan = os.getenv(f"{data['c']}_CHANNEL")
    if not chan:
        return await message.answer(f"❌ .env da {data['c']}_CHANNEL topilmadi.")

    allowed = any([message.video, message.photo, message.voice, message.text, message.document, message.audio])
    if not allowed:
        return await message.answer("⚠️ Faqat text, photo, video, voice, audio yoki document yuboring.")

    try:
        sent = await bot.copy_message(chan, message.chat.id, message.message_id)

        if message.video:
            c_type = "video"
        elif message.photo:
            c_type = "photo"
        elif message.voice:
            c_type = "voice"
        elif message.audio:
            c_type = "audio"
        elif message.document:
            c_type = "document"
        else:
            c_type = "text"

        await db.add_content_item(
            data['c'],
            data['d'],
            c_type,
            str(sent.message_id),
            message.caption or message.text or "Dars",
            ""
        )
        await message.answer("✅ Qo'shildi. Yana yuboring...")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

# ==========================================================
#              7. QIDIRUV VA STATISTIKA
# ==========================================================

@admin_router.message(F.text == "🔍 Qidiruv")
async def search_ask(message: types.Message, state: FSMContext):
    await message.answer(
        "🔎 <b>Qidiruv Rejimi</b>\n"
        "Quyidagilardan birini yozing:\n"
        "🔹 6 xonali ID (Masalan: <code>123456</code>)\n"
        "🔹 Telefon raqam\n"
        "🔹 Ism",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.search_user)

@admin_router.message(AdminState.search_user)
async def search_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy Menyu":
        return await back_to_home(message, state)

    user = await db.search_user_universal(message.text)
    if not user:
        return await message.answer(
            "❌ <b>Topilmadi.</b> Qayta urinib ko'ring:",
            reply_markup=back_kb(),
            parse_mode="HTML"
        )

    s_icon = "🟢" if user['status'] == 'ACTIVE' else "🟡" if user['status'] == 'PENDING_APPROVAL' else "🔴"

    text = (
        f"👤 <b>TOPILDI:</b>\n"
        f"🆔 <code>{user['six_digit_id']}</code>\n"
        f"📛 <b>Ism:</b> {user['full_name']}\n"
        f"📞 <b>Tel:</b> {user['phone']}\n"
        f"📊 <b>Status:</b> {s_icon} {user['status']}"
    )

    kb_rows = []
    if user['status'] == 'PENDING_APPROVAL':
        kb_rows.append([
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user['user_id']}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user['user_id']}")
        ])
    elif user['status'] == 'ACTIVE':
        kb_rows.append([InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"reject_{user['user_id']}")])
    else:
        kb_rows.append([InlineKeyboardButton(text="🔓 Aktivlashtirish", callback_data=f"approve_{user['user_id']}")])

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode="HTML"
    )

@admin_router.message(F.text == "📊 Statistika")
async def stats_show(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Hamma (Excel)", callback_data="export_ALL")],
        [InlineKeyboardButton(text="📥 Faol (Excel)", callback_data="export_ACTIVE")]
    ])

    all_u = await db.get_users_by_status("ALL")
    active_u = await db.get_users_by_status("ACTIVE")

    text = (
        f"📊 <b>LOYIHA STATISTIKASI</b>\n\n"
        f"👥 Jami userlar: <b>{len(all_u)}</b>\n"
        f"🟢 Faol o'quvchilar: <b>{len(active_u)}</b>"
    )

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("export_"))
async def export_handler(call: CallbackQuery):
    await call.answer()
    status = call.data.split("_")[1]
    users = await db.get_users_by_status(status)

    if not users:
        return await call.answer("Ma'lumot topilmadi", show_alert=True)

    await call.message.answer("⏳ <b>Excel fayl tayyorlanmoqda...</b>", parse_mode="HTML")

    try:
        df = pd.DataFrame([dict(u) for u in users])
        fname = f"users_{status}.xlsx"
        df.to_excel(fname, index=False)
        await call.message.answer_document(FSInputFile(fname), caption=f"📊 {status} Userlar ro'yxati")
        os.remove(fname)
    except Exception as e:
        await call.message.answer(f"❌ Xatolik: {e}")

# ==========================================================
#              8. QO'LLANMA VA XABAR YUBORISH
# ==========================================================

@admin_router.message(F.text == "📖 Qo'llanma")
async def manual_ask(message: types.Message, state: FSMContext):
    link = await db.get_manual_link()
    await message.answer(
        f"📖 <b>Qo'llanma Linki:</b>\n{link}\n\nYangilash uchun yangi linkni yuboring:",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminState.manual_update)

@admin_router.message(AdminState.manual_update)
async def manual_save(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy Menyu":
        return await back_to_home(message, state)
    await db.save_manual_link(message.text)
    await message.answer("✅ <b>Qo'llanma linki yangilandi!</b>", reply_markup=admin_home_kb(), parse_mode="HTML")
    await state.clear()

@admin_router.message(F.text == "📢 Xabar Yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Hammaga"), KeyboardButton(text="✅ Faollarga")],
        [KeyboardButton(text="⏳ Tasdiqlanmaganlarga"), KeyboardButton(text="🔙 Asosiy Menyu")]
    ], resize_keyboard=True)

    await message.answer("📢 <b>Kimga xabar yuboramiz?</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminState.broadcast_type)

@admin_router.message(AdminState.broadcast_type)
async def broadcast_msg(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy Menyu":
        return await back_to_home(message, state)

    target = "ALL"
    if "Faol" in message.text:
        target = "ACTIVE"
    elif "Tasdiqlan" in message.text:
        target = "PENDING_APPROVAL"

    await state.update_data(target=target)
    await message.answer(f"📝 <b>Xabarni yuboring:</b>", reply_markup=back_kb(), parse_mode="HTML")
    await state.set_state(AdminState.broadcast_msg)

@admin_router.message(AdminState.broadcast_msg)
async def broadcast_send(message: types.Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Asosiy Menyu":
        return await back_to_home(message, state)

    data = await state.get_data()
    target_status = data['target']

    all_users = await db.get_users_by_status("ALL")
    users_to_send = [u for u in all_users if target_status == "ALL" or u['status'] == target_status]

    if not users_to_send:
        await message.answer("❌ Bu toifada userlar topilmadi.", reply_markup=admin_home_kb())
        await state.clear()
        return

    msg_count = 0
    await message.answer(
        f"🚀 <b>Xabar yuborish boshlandi...</b> (Jami: {len(users_to_send)} ta)",
        parse_mode="HTML"
    )

    for u in users_to_send:
        try:
            await bot.copy_message(
                chat_id=u['user_id'],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            msg_count += 1
        except Exception:
            pass

    await message.answer(
        f"✅ <b>Muvaffaqiyatli yuborildi:</b> {msg_count} ta userga.",
        reply_markup=admin_home_kb(),
        parse_mode="HTML"
    )
    await state.clear()
