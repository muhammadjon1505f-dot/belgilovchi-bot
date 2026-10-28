"""
Belgilovchi Bot — Konfiguratsiya fayli.
"""
import os

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8976783740:AAHg9cLCSDxpWYWAI_3Mz-0369M3HsjO43o")

# Bot egasining Telegram ID si (admin buyruqlari uchun)
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8191930658").split(",") if x.strip().isdigit()]

# Render va Web Server porti
PORT = int(os.environ.get("PORT", 8088))

# Guruhda admin chaqirish o'rtasidagi antispam vaqti (soniyalarda)
ADMIN_CALL_COOLDOWN = int(os.environ.get("ADMIN_CALL_COOLDOWN", 20))

# A'zolarni guruhda tag qilish parametrlari
TAG_BATCH_SIZE = 5
TAG_DELAY_SECONDS = 1.5

# Ma'lumotlar bazasi manzili
DATABASE_PATH = os.environ.get("DATABASE_PATH", "belgilovchi.db")
