# Belgilovchi Bot (@Belgilaydibot) — 24/7 Guruh Administratorlarini Chaqiruvchi Bot

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/muhammadjon1505f-dot/belgilovchi-bot)

Ushbu bot Telegram guruhlarida a'zolar va administratorlar o'rtasidagi aloqani tezlashtirish, qoidabuzarliklar haqida darhol ogohlantirish va guruh a'zolariga e'lon tarqatish uchun ishlab chiqilgan.

---

## ⚡ Asosiy Imkoniyatlar

1. **Adminlarni bir zumda chaqirish (`@admin`, `@admins`):**
   - Guruhdagi admin foydalanuvchi `@admin [sabab]` yoki `@admins [sabab]` deb yozsa, bot guruhdagi barcha adminlarni topib, ularni bir xabarda metka (mention) qiladi.
   - `/admin` buyrug'i olib tashlangan va admin bo'lmagan foydalanuvchilar (unadminlar) uchun ishlamaydi.
   - Barcha adminlarga zudlik bilan push-bildirishnoma (notification) boradi.
   - 20 soniyalik antispam (cooldown) cheklovi mavjud.

2. **A'zolarni metka qilish (`/tag`, `/all`, `/metka`):**
   - Faqat guruh adminlari uchun ruxsat etilgan.
   - Guruhdagi faol a'zolarni 5 tadan bo'lib spam-filtrga tushmasdan e'lon bilan belgilaydi.

3. **Statistika va Ma'lumotlar Bazasi:**
   - SQLite WAL rejimida ishlaydi.
   - Bot ulangan guruhlar va foydalanuvchilar soni saqlanadi.
   - `/stats` buyrug'i orqali bot egasi ko'rsatkichlarni ko'ra oladi.

4. **24/7 Ishlash Uchun O'rnatilgan Web Server:**
   - Ichki HTTP health-check serveri (`/healthz`) mavjud.
   - Render.com, Koyeb, Railway kabi platformalarda xizmat uxlamay 24/7 ishlashi uchun moslashtirilgan.

---

## 🚀 1. Hozirgi Serverda (Linux / VPS / Termux) 24/7 Ishga Tushirish

Botni fonda uzluksiz ishlatish uchun:

```bash
cd /root/belgilovchi-bot
nohup python3 bot.py > bot.log 2>&1 &
```

Loglarni tekshirish:
```bash
tail -f /root/belgilovchi-bot/bot.log
```

---

## ☁️ 2. Render.com ga 24/7 Bepul Joylashtirish (Tavsiya etiladi)

Render.com da botni bepul va 24/7 ishlatish bo'yicha qadam-baqadam ko'rsatma:

1. **GitHub Repozitoriy oching:**
   - GitHub profilingizda yangi repozitoriy yarating (masalan: `belgilovchi-bot`).
   - Ushbu papkadagi barcha fayllarni GitHub repozitoriyingizga yuklang (`git push`).

2. **Render.com da yangi Web Service oching:**
   - [https://render.com](https://render.com) ga kiring (GitHub orqali bepul ro'yxatdan o'ting).
   - **New +** -> **Web Service** ni bosing.
   - O'zingizning `belgilovchi-bot` repozitoriyingizni tanlang.

3. **Sozlamalar:**
   - **Name:** `belgilovchi-bot`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** `Free`

4. **Environment Variables (Muhit O'zgaruvchilari):**
   - `BOT_TOKEN` = `<SIZNING_BOT_TOKENINGIZ>`
   - `PORT` = `10000`

5. **Deploy tugmasini bosing!**

> 💡 **24/7 Uxlamasdan Ishlash Sirlari (Keep-Alive):**
> Render.com bepul servislari 15 daqiqa murojaat bo'lmasa uxlab qoladi.
> Botimizda ichki `/healthz` HTTP serveri borligi sababli:
> 1. [https://uptimerobot.com](https://uptimerobot.com) saytida bepul ro'yxatdan o'ting.
> 2. Yangi HTTP Monitor qo'shing: `https://sizning-servisingiz.onrender.com/healthz`
> 3. Monitoring intervalini **5 yoki 10 daqiqa** qilib belgilang.
> Natijada UptimeRobot har 5 daqiqada botingizga signal berib turadi va bot Render.com da **24/7 bir umr bepul** ishlab turadi!

---

## 🌐 3. Boshqa Bepul VPS / Cloud Alternativalari

1. **Koyeb.com:**
   - Bepul Docker / Web Service qo'llab-quvvatlaydi.
   - `Dockerfile` orqali to'g'ridan-to'g'ri ishga tushadi.

2. **Oracle Cloud Free Tier:**
   - 4 OCPU, 24 GB RAM bepul doimiy VPS beradi (Ubuntu).
   - `systemd` orqali 24/7 botni ishlatish uchun ideal.

3. **Railway.app / Fly.io:**
   - Dockerfile orqali 1 komanda bilan deploy qilinadi (`fly launch`).
