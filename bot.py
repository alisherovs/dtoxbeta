import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# 1. .ENV VA SOZLAMALAR
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

# 2. MODULLAR
from admin import admin_router
from user import user_router, kb_dashboard, UserState, kb_walk_check
import database as db
from ai_service import get_daily_ai_broadcast

# ==========================================
# 🌅 ERTALABGI TARQATISH (07:00)
# ==========================================
async def morning_distribution(bot: Bot, dp: Dispatcher):
    logging.info("🌅 Tongi kontent tarqatish boshlandi...")
    users = await db.get_users_by_status("ACTIVE")
    
    for user in users:
        uid = user['user_id']
        current_course = user.get('current_course')
        if not current_course: continue
            
        next_day = user['current_day'] + 1
        all_content = await db.get_day_content_list(current_course, next_day)
        
        # Faqat extra = 'morning' (yoki bo'sh qolgan eski fayllarni) olamiz
        morning_content = [item for item in all_content if item.get('extra') in ['morning', '', None]]
        
        if morning_content:
            await db.increment_user_day(uid) # Kunni oshiramiz
            channel = os.getenv(f"{current_course}_CHANNEL")
            
            try:
                await bot.send_message(uid, f"☀️ <b>Xayrli tong, {user['full_name']}!</b>\n🚀 <b>{next_day}-kun</b> mashqlari tayyor. Olg'a!", reply_markup=kb_dashboard(), parse_mode="HTML")
                for item in morning_content:
                    await bot.copy_message(chat_id=uid, from_chat_id=channel, message_id=int(item['file_id']))
                
                await bot.send_message(uid, "Mashqlarni bajarishni unutmang! Kechqurun navbatdagi darslar va hisobot so'raladi.", parse_mode="HTML")
            except TelegramAPIError:
                pass

# ==========================================
# 🌃 KECHKI TARQATISH VA HISOBOT (20:00)
# ==========================================
async def evening_distribution(bot: Bot, dp: Dispatcher):
    logging.info("🌃 Kechki kontent va Hisobot so'rash boshlandi...")
    users = await db.get_users_by_status("ACTIVE")
    
    for user in users:
        uid = user['user_id']
        current_course = user.get('current_course')
        current_day = user.get('current_day')
        
        if not current_course or current_day == 0: continue
            
        all_content = await db.get_day_content_list(current_course, current_day)
        evening_content = [item for item in all_content if item.get('extra') == 'evening']
        channel = os.getenv(f"{current_course}_CHANNEL")
        
        try:
            # 1. Agar kechki media bo'lsa, tashlab beramiz
            if evening_content:
                await bot.send_message(uid, "🌙 <b>Kechki qo'shimcha darsliklarimiz:</b>", parse_mode="HTML")
                for item in evening_content:
                    await bot.copy_message(chat_id=uid, from_chat_id=channel, message_id=int(item['file_id']))
            
            # 2. Avtomatik Hisobot so'rash holatiga o'tkazamiz
            ctx = FSMContext(storage=dp.storage, key=StorageKey(bot.id, uid, uid))
            await ctx.set_state(UserState.reporting_in)
            
            await bot.send_message(
                uid, 
                "📊 <b>KUNLIK HISOBOT VAQTI!</b>\n\nBugun jami qancha kaloriya qabul qildingiz? (Faqat raqam yozing):", 
                parse_mode="HTML",
                reply_markup=types.ReplyKeyboardRemove()
            )
        except TelegramAPIError:
            pass

# ==========================================
# 🤖 AI MASLAHATCHI (Ixtiyoriy vaqtlar)
# ==========================================
async def ai_daily_reminder(bot: Bot, time_of_day: str):
    logging.info(f"🤖 {time_of_day} uchun AI xabar tarqatilmoqda...")
    try:
        ai_message = await get_daily_ai_broadcast(time_of_day)
        users = await db.get_users_by_status("ACTIVE")
        
        for user in users:
            markup = kb_walk_check() if time_of_day == "tushlik" else None # Tushlikda yurishni so'raymiz
            try: 
                await bot.send_message(user['user_id'], f"👋 <b>{user['full_name']}</b>, botimizdan maslahat:\n\n{ai_message}", parse_mode="HTML", reply_markup=markup)
            except TelegramAPIError: pass
    except Exception as e:
        logging.error(f"❌ AI Reminder xatolik: {e}")


# ==========================================
# ASOSIY START QISMI
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout)
    await db.init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
    # Ertalab 07:00 da darslar
    scheduler.add_job(morning_distribution, trigger='cron', hour=7, minute=0, kwargs={'bot': bot, 'dp': dp})
    # Kechqurun 20:00 da kechki fayllar va hisobot
    scheduler.add_job(evening_distribution, trigger='cron', hour=20, minute=0, kwargs={'bot': bot, 'dp': dp})
    # AI xabarlar
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=13, minute=0, kwargs={'bot': bot, 'time_of_day': 'tushlik'})
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
