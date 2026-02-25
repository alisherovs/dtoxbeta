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

# 2. KEYIN BOSHQA FAYLLARNI CHAQIRAMIZ!
from admin import admin_router
from user import user_router, kb_dashboard, UserState, kb_walk_check
import database as db
from ai_service import get_daily_ai_broadcast 

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ... (buyog'i o'zgarishsiz qoladi, async def morning_distribution... va hokazo)

async def morning_distribution(bot: Bot, dp: Dispatcher):
    logging.info("⏰ Tongi tarqatish boshlandi...")
    users = await db.get_users_by_status("ACTIVE")
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    
    for user in users:
        uid = user['user_id']
        if user['last_report_date'] and str(user['last_report_date']) >= str(yesterday):
            next_day = user['current_day'] + 1
            if await db.get_day_content_list(user['current_course'], next_day):
                await db.increment_user_day(uid)
                ctx = FSMContext(storage=dp.storage, key=StorageKey(bot.id, uid, uid))
                await ctx.set_state(UserState.dashboard)
                try: await bot.send_message(uid, f"☀️ <b>Xayrli tong, {user['full_name']}!</b>\n🚀 Bugun <b>{next_day}-kun</b> ochildi.", parse_mode="HTML", reply_markup=kb_dashboard())
                except: pass
        elif not user['last_report_date'] or str(user['last_report_date']) < str(yesterday):
             try: await bot.send_message(uid, "⚠️ <b>Eslatma:</b> Kechagi hisobotni topshirmadingiz!", parse_mode="HTML", reply_markup=kb_dashboard())
             except: pass

async def ai_daily_reminder(bot: Bot, time_of_day: str):
    logging.info(f"🤖 {time_of_day} uchun AI xabar...")
    ai_message = await get_daily_ai_broadcast(time_of_day)
    users = await db.get_users_by_status("ACTIVE")
    
    for user in users:
        markup = kb_walk_check() if time_of_day == "kechqurun" else None
        try: await bot.send_message(user['user_id'], f"👋 <b>{user['full_name']}</b>, botimizdan maslahat:\n\n{ai_message}", parse_mode="HTML", reply_markup=markup)
        except: pass

async def main():
    await db.init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(morning_distribution, trigger='cron', hour=7, minute=0, kwargs={'bot': bot, 'dp': dp})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=8, minute=0, kwargs={'bot': bot, 'time_of_day': 'ertalab'})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=12, minute=0, kwargs={'bot': bot, 'time_of_day': 'tushlik'})
    scheduler.add_job(ai_daily_reminder, trigger='cron', hour=17, minute=0, kwargs={'bot': bot, 'time_of_day': 'kechqurun'})
    scheduler.start()
    
    print("🚀 Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())