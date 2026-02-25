import aiosqlite
import datetime

DB_NAME = "dtoxfit.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, full_name TEXT, phone TEXT, age INTEGER, weight REAL, 
            six_digit_id INTEGER, status TEXT DEFAULT 'PENDING_APPROVAL', current_course TEXT, 
            current_day INTEGER DEFAULT 1, start_date DATE, last_report_date DATE, report_submitted_today BOOLEAN DEFAULT 0)""")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, options TEXT, correct_index INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS courses (course_code TEXT PRIMARY KEY, total_days INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS course_content (id INTEGER PRIMARY KEY AUTOINCREMENT, course_code TEXT, day INTEGER, content_type TEXT, file_id TEXT, caption TEXT)")
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor: return await cursor.fetchone()

async def add_user(user_id, full_name, phone, age, weight, six_digit_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, full_name, phone, age, weight, six_digit_id) VALUES (?, ?, ?, ?, ?, ?)", 
                         (user_id, full_name, phone, age, weight, six_digit_id))
        await db.commit()

async def get_pending_users_paginated(page, limit):
    offset = (page - 1) * limit
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) as count FROM users WHERE status = 'PENDING_APPROVAL'") as c: total = (await c.fetchone())['count']
        async with db.execute("SELECT * FROM users WHERE status = 'PENDING_APPROVAL' LIMIT ? OFFSET ?", (limit, offset)) as c: users = await c.fetchall()
        return users, total

async def update_user_status(user_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        await db.commit()

async def get_intro():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT value as file_id, (SELECT value FROM settings WHERE key='intro_caption') as caption FROM settings WHERE key='intro_video'") as c: return await c.fetchone()

async def save_intro(file_id, caption):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('intro_video', ?)", (file_id,))
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('intro_caption', ?)", (caption,))
        await db.commit()

async def get_all_quizzes():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM quizzes") as cursor: return await cursor.fetchall()

async def add_quiz(question, options, correct_index):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO quizzes (question, options, correct_index) VALUES (?, ?, ?)", (question, "|".join(options), correct_index))
        await db.commit()

async def delete_quiz(quiz_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
        await db.commit()

async def get_course_days(course_code):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT total_days FROM courses WHERE course_code = ?", (course_code,)) as c: 
            res = await c.fetchone()
            return res[0] if res else 0

async def set_course_days(course_code, total_days):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO courses (course_code, total_days) VALUES (?, ?)", (course_code, total_days))
        await db.commit()

async def get_day_content_list(course_code, day):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM course_content WHERE course_code = ? AND day = ?", (course_code, day)) as cursor: return await cursor.fetchall()

async def add_content_item(course_code, day, content_type, file_id, caption, _):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO course_content (course_code, day, content_type, file_id, caption) VALUES (?, ?, ?, ?, ?)", 
                         (course_code, day, content_type, file_id, caption))
        await db.commit()

async def delete_day_content(course_code, day):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM course_content WHERE course_code = ? AND day = ?", (course_code, day))
        await db.commit()

async def search_user_universal(query):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE six_digit_id LIKE ? OR phone LIKE ? OR full_name LIKE ?", (f"%{query}%", f"%{query}%", f"%{query}%")) as c: return await c.fetchone()

async def get_users_by_status(status):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM users" if status == "ALL" else "SELECT * FROM users WHERE status = ?"
        params = () if status == "ALL" else (status,)
        async with db.execute(query, params) as cursor: return await cursor.fetchall()

async def get_manual_link():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key='manual_link'") as c: 
            res = await c.fetchone()
            return res[0] if res else "https://t.me/"

async def save_manual_link(link):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('manual_link', ?)", (link,))
        await db.commit()

async def start_user_course(user_id, course_code):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET current_course = ?, current_day = 1, start_date = ?, report_submitted_today = 0 WHERE user_id = ?", 
                         (course_code, datetime.date.today(), user_id))
        await db.commit()

async def save_report(user_id, course, day, cal_in, cal_out):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET report_submitted_today = 1, last_report_date = ? WHERE user_id = ?", (datetime.date.today(), user_id))
        await db.commit()

async def increment_user_day(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET current_day = current_day + 1, report_submitted_today = 0 WHERE user_id = ?", (user_id,))
        await db.commit()