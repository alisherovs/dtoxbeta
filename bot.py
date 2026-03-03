import asyncio
import logging
import sys
import os
import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 1. ENG AVAL .ENV NI YUKLAYMIZ!
from dotenv import load_dotenv
load_dotenv()

# 2. CONFIG VA ADMIN IDLARNI TO'G'RILASH
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Agar .env dagi ADMIN_ID vergul bilan yozilgan bo'lsa (masalan: "8008006509, 8008157657")
# Quyidagi qator ularni xatosiz "List of Integers" ga aylantiradi:
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "")
ADMIN_IDS = [int(i.strip()) for i in ADMIN_ID_RAW.split(",") if i.strip().isdigit()]

# 3. KEYIN BOSHQA FAYLLARNI CHAQIRAMIZ!
# (Fayllaringiz papka ichida to'g'ri turganligiga ishonch hosil qiling)
from admin import admin_router
from user import user_router, kb_dashboard, UserState, kb_walk_check
import database as db
from ai_service import get_daily_ai_broadcast

# Jurnalni yoqish
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


# ==========================================
# AVTOMATLASHTIRILGAN FUNKSIYALAR (Scheduler)
# ==========================================

async def morning_distribution(bot: Bot, dp: Dispatcher):
    logging.info("⏰ Tongi tarqatish boshlandi...")
    try:
        users = await db.get_users_by_status("ACTIVE")
    except Exception as e:
        logging.error(f"Bazadan userlarni olishda xatolik: {e}")
        return

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    
    for user in users:
        uid = user['user_id']
        try:
            if user['last_report_date'] and str(user['last_report_date']) >= str(yesterday):
                next_day = user['current_day'] + 1
                
                if await db.get_day_content_list(user['current_course'], next_day):
                    await db.increment_user_day(uid)
                    
                    # FSM state'ni to'g'ridan to'g'ri yangilash
                    ctx = FSMContext(storage=dp.storage, key=StorageKey(bot.id, uid, uid))
                    await ctx.set_state(UserState.dashboard)
                    
                    try: 
                        await bot.send_message(
                            uid, 
                            f"☀️ <b>Xayrli tong, {user['full_name']}!</b>\n🚀 Bugun <b>{next_day}-kun</b> ochildi.", 
                            parse_mode="HTML", 
                            reply_markup=kb_dashboard()
                        )
                    except Exception as e: 
                        logging.warning(f"{uid} ga xabar yuborib bo'lmadi: {e}")
                        
            elif not user['last_report_date'] or str(user['last_report_date']) < str(yesterday):
                try: 
                    await bot.send_message(
                        uid, 
                        "⚠️ <b>Eslatma:</b> Kechagi hisobotni topshirmadingiz!", 
                        parse_mode="HTML", 
                        reply_markup=kb_dashboard()
                    )
                except Exception as e: 
                    logging.warning(f"{uid} ga eslatma yuborib bo'lmadi: {e}")
        except Exception as e:
            logging.error(f"User {uid} uchun tsikl ichida xato: {e}")


async def ai_daily_reminder(bot: Bot, time_of_day: str):
    logging.info(f"🤖 {time_of_day} uchun AI xabar...")
    try:
        ai_message = await get_daily_ai_broadcast(time_of_day)
        users = await db.get_users_by_status("ACTIVE")
        
        for user in users:
            markup = kb_walk_check() if time_of_day == "kechqurun" else None
            try: 
                await bot.send_message(
                    user['user_id'], 
                    f"👋 <b>{user['full_name']}</b>, botimizdan maslahat:\n\n{ai_message}", 
                    parse_mode="HTML", 
                    reply_markup=markup
                )
            except Exception as e: 
                pass # Bloklagan bo'lsa o'tkazib yuboramiz
    except Exception as e:
        logging.error(f"AI Reminderda umumiy xatolik: {e}")


# ==========================================
# ASOSIY BOTNI ISHGA TUSHIRISH
# ==========================================

async def main():
    # Baza yuklanishi
    await db.init_db()
    
    # Bot va Dispatcher yaratilishi
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    # ROUTERLARNI ULANISHI (TARTIBI MUHIM)
    dp.include_router(admin_router) # Admin doim birinchi tursin!
    dp.include_router(user_router)
    
    # SCHEDULER (Vaqtli vazifalar)
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(morning_distribution, trigger='cron', hour=7, minute=0, kwargs={'bot': bot, 'dp': dp})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=8, minute=0, kwargs={'bot': bot, 'time_of_day': 'ertalab'})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=12, minute=0, kwargs={'bot': bot, 'time_of_day': 'tushlik'})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=17, minute=0, kwargs={'bot': bot, 'time_of_day': 'kechqurun'})
    scheduler.start()
    
    logging.info(f"✅ Tizim yuklandi! Bosh Adminlar ro'yxati: {ADMIN_IDS}")
    logging.info("🚀 Bot muvaffaqiyatli ishga tushdi va xabarlar kutyapti...")
    
    # Eski/osilib qolgan xabarlarni tozalab tashlash va ishga tushish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
