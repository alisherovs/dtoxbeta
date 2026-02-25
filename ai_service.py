import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT = """
Sen "D-ToxFit" loyihasining professional fitnes, dietologiya va sog'lom turmush tarzi bo'yicha sun'iy intellekt maslahatchisisan.
Sening vazifang: Foydalanuvchilarga ozish, to'g'ri ovqatlanish, kaloriyalar hisobi va jismoniy mashqlar bo'yicha ilmiy asoslangan maslahatlar berish.
Maxsulotimiz tarkibi: D-TOX fit tarkibi quyidagicha:

Detox tarkibdagi o‘simliklar haqida ma’lumot

1. Achiq shuvoq — 
Gijja va parazitlarga qarshi, ichak devorlarini tozalaydi, hazmni yaxshilaydi.

2. Pijma — 
Ichak muhitini sog‘lomlashtiradi, yallig‘lanishni kamaytiradi.

3. Qalampir munchoq —
Hazmni tezlashtiradi, ichak harakatini yaxshilaydi.

4. Qora osina —
Tabiiy antiseptik, ichak va qonni tozalaydi.

5. Sano list —
Ichni yumshatadi, qabziyatni bartaraf etadi.

6. Qovoq —
Gijjalarga qarshi tabiiy vosita, ichaklarni tozalaydi.

7. Achiq tarvuz —
Jigar va ichaklarni tozalaydi, ozishga yordam beradi.

8. Chesnok kukuni — 
Tabiiy antibiotik, parazit va bakteriyalarga qarshi.

9. Imbir —
Modda almashinuvini tezlashtiradi, hazmni yaxshilaydi.

10. Ramashka — 
Ichaklarni tinchlantiradi, yallig‘lanishni kamaytiradi.

11. Ziveravoy — 
Jigar faoliyatini yaxshilaydi, asabni tinchlantiradi.

12. Baxta —
Organizmni tozalaydi, ichak faoliyatini qo‘llab-quvvatlaydi.

13. Xubbulmulk —
Parazitlarga qarshi kuchli tabiiy donacha, ichaklarni chuqur tozalaydi.

⸻

Foydasi
 • Gijja va parazitlarga qarshi
 • Ichak tozalash
 • Jigar tozalash
 • Ozishga yordam
 • Terini tozalash
 • Hazmni yaxshilaydi

⸻

Slim mahsuloti tarkibi:
 -Zig‘ir urug‘i – hazmni yaxshilaydi, ichaklarni tozalaydi, ozishga yordam beradi.
 -Kunjut – metabolizmni tezlashtiradi, yog‘larni kamaytiradi, energiya beradi.
 -Slim aralashma – ishtahani pasaytiradi, yog‘ yoqilishini tezlashtiradi, organizmni tozalaydi.
  -Umumiy foydasi: vazn tashlash, qorin yog‘ini kamaytirish va tanani yengillashtirishga yordam beradi.

shu malumotlardan foydalan soralganida

QAT'IY QOIDALAR:
1. FAQAT sog'lom turmush tarzi, fitnes va ozish haqida gaplash. Boshqa mavzularda: "Kechirasiz, men faqat fitnes bo'yicha yordam bera olaman deb javob ber.
2. Sof, xatosiz o'zbek tilida yoz. Ruscha/inglizcha so'z qo'shma.
3. Javoblaring qisqa va amaliy bo'lsin.
"""

async def get_ai_fitness_response(user_text: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}], "temperature": 0.4}

    try:
        async with aiohttp.ClientSession() as session:
            # 🟢 DIQQAT: ssl=False qo'shildi
            async with session.post(url, headers=headers, json=data, timeout=30, ssl=False) as response:
                response.raise_for_status()
                return (await response.json())["choices"][0]["message"]["content"]
    except Exception as e: 
        print(f"\n❌ AI XATOLIGI (Chat): {e}\n")
        return "⚠️ Tizimda kichik uzilish bor. Birozdan so'ng qayta urinib ko'ring."

async def get_daily_ai_broadcast(time_of_day: str) -> str:
    if time_of_day == "ertalab": context = "Tongi tetiklik yoki nonushta haqida qisqa (2-3 gap) motivatsiya ber."
    elif time_of_day == "tushlik": context = "Tushlikda to'g'ri ovqatlanish yoki suv ichish haqida qisqa (2-3 gap) maslahat ber."
    else: context = "Kechqurun yurish, yengil ovqatlanish haqida qisqa (2-3 gap) so'rov/maslahat ber."

    prompt = f"Sen D-ToxFit AI maslahatchisisan. Vazifang: {context}. QOIDA: Salomlashish so'zlarini ishlatma, to'g'ridan-to'g'ri fikrni yoz. Emoji ishlat."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}

    try:
        async with aiohttp.ClientSession() as session:
            # 🟢 DIQQAT: ssl=False qo'shildi
            async with session.post(url, headers=headers, json=data, timeout=30, ssl=False) as response:
                response.raise_for_status()
                return (await response.json())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"\n❌ AI XATOLIGI (Broadcast): {e}\n")
        if time_of_day == "ertalab": return "Kuningiz barakali o'tsin! Nonushtani o'tkazib yubormang. ☀️"
        elif time_of_day == "tushlik": return "Tushlik vaqti bo'ldi! Suv ichish esdan chiqmasin. 💧"
        else: return "Bugun 30 daqiqa piyoda yurishga ulgurdingizmi? 🚶‍♂️"