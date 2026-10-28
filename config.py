"""
Belgilovchi Bot — Xavfsiz Konfiguratsiya Moduli.
Xavfsizlik talablariga muvofiq, maxfiy kalitlar kod ichida qat'iy saqlanmaydi.
"""
import os
from pathlib import Path

# Mahalliy .env faylini xavfsiz o'qish (agar mavjud bo'lsa)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

# Telegram Bot Token (Faqat muhit o'zgaruvchisidan olinadi)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError(
        "XAVFSIZLIK XATOSI: BOT_TOKEN topilmadi! "
        "Tokenni muhit o'zgaruvchisi (Environment Variable) yoki .env orqali belgilang."
    )

# Bot egasining Telegram ID si (admin buyruqlari uchun)
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8191930658").split(",") if x.strip().isdigit()]

# Render va Web Server porti
PORT = int(os.environ.get("PORT", 8088))

# Guruhda admin chaqirish o'rtasidagi antispam vaqti (soniyalarda)
ADMIN_CALL_COOLDOWN = int(os.environ.get("ADMIN_CALL_COOLDOWN", 20))

# Butun guruh bo'yicha global antispam (1 daqiqada maksimum 5 ta admin chaqiruv)
GROUP_MAX_CALLS_PER_MINUTE = int(os.environ.get("GROUP_MAX_CALLS_PER_MINUTE", 5))

# A'zolarni guruhda tag qilish parametrlari
TAG_BATCH_SIZE = 5
TAG_DELAY_SECONDS = 1.5

# Ma'lumotlar bazasi manzili
DATABASE_PATH = os.environ.get("DATABASE_PATH", "belgilovchi.db")
