"""
Belgilovchi Bot (@Belgilaydibot)
Guruhlarni boshqarish va adminlarni bir zumda avtomatik metka qilish (chaqirish) boti.
"""
import time
import html
import logging
import threading
import telebot
from telebot import types

import config
from database import Database
from web_server import start_health_server_in_background
from cron_manager import CronManager

# Logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("BelgilovchiBot")

# Initialize DB and Bot
db = Database(config.DATABASE_PATH)
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# In-memory trackers
user_cooldowns = {}         # (chat_id, user_id) -> timestamp
group_call_history = {}     # chat_id -> list of recent call timestamps (antiraid)
active_tags = set()         # chat_ids currently running /tag process

# Initialize 10 Internal Automated Crons
cron_manager = CronManager(bot, db, user_cooldowns, active_tags, group_call_history)

def escape_html(text: str) -> str:
    if not text:
        return ""
    return html.escape(str(text))

def format_user_mention(user) -> str:
    """Foydalanuvchini kliklanadigan mention ko'rinishida formatlash."""
    if user.username:
        return f"@{user.username}"
    name = escape_html(user.first_name or "Foydalanuvchi")
    return f"<a href='tg://user?id={user.id}'>{name}</a>"

def is_chat_admin(chat_id: int, user_id: int) -> bool:
    """Foydalanuvchi guruh admini ekanligini tekshirish."""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception as e:
        logger.error(f"Admin tekshirishda xatolik: {e}")
        return False

# ==================== BUYRUQLAR: START VA HELP ====================

@bot.message_handler(commands=["start", "help"])
def handle_start(message: types.Message):
    user = message.from_user
    db.add_or_update_user(user.id, user.first_name, user.username)

    if message.chat.type in ("group", "supergroup"):
        db.add_or_update_group(message.chat.id, message.chat.title, message.chat.username)
        bot.reply_to(
            message,
            "👋 <b>Belgilovchi bot guruhda faol!</b>\n\n"
            "Adminlarni chaqirish uchun <code>/admin</code> yoki <code>@admin</code> deb yozing."
        )
        return

    # Shaxsiy chatda xush kelibsiz xabari — faqat bitta '➕ Guruhga qo'shish' tugmasi bilan
    bot_info = bot.get_me()
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add = types.InlineKeyboardButton(
        "➕ Guruhga qo'shish",
        url=f"https://t.me/{bot_info.username}?startgroup=true"
    )
    markup.add(btn_add)

    text = (
        f"👋 Assalomu alaykum, {escape_html(user.first_name)}!\n\n"
        f"⚡ Men Belgilovchi bot (@{bot_info.username}) — guruhlarda adminlarni va a'zolarni "
        f"bir zumda chaqirib (metka / tag qilib) beruvchi professional botman.\n\n"
        f"👑 Guruhda:\n"
        f"• /admin [sabab] — Barcha adminlarni zudlik bilan chaqiradi.\n"
        f"• @admin [sabab] — Xabarga javob berib yozilsa, qoidabuzarlik haqida xabar beradi.\n"
        f"• /tag [xabar] — Guruh a'zolariga e'lon yuborish (faqat adminlar uchun).\n\n"
        f"🚀 Ishlatish: Quyidagi tugma orqali botni guruhingizga qo'shing va adminlik bering!"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ==================== ADMIN CHAQIRISH (/admin, @admin, /admins) ====================

@bot.message_handler(commands=["admin", "admins", "calladmin", "report"])
def handle_admin_call_command(message: types.Message):
    trigger_admin_call(message)

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and m.text and any(w in m.text.lower() for w in ("@admin", "@admins", "/admin", "/admins")))
def handle_admin_mention(message: types.Message):
    trigger_admin_call(message)

def trigger_admin_call(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user

    if message.chat.type not in ("group", "supergroup"):
        bot_info = bot.get_me()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Guruhga qo'shish", url=f"https://t.me/{bot_info.username}?startgroup=true"))
        bot.reply_to(message, "ℹ️ Bu buyruq faqat guruhlarda ishlaydi. Botni guruhingizga qo'shing!", reply_markup=markup)
        return

    # Guruh va a'zoni bazada saqlash
    db.add_or_update_group(chat_id, message.chat.title, message.chat.username)
    db.track_member_activity(chat_id, user.id, user.first_name, user.username)

    # Cooldown (antispam) tekshirish
    now = time.time()
    last_call = user_cooldowns.get((chat_id, user.id), 0)
    cooldown = config.ADMIN_CALL_COOLDOWN

    # 1. Guruh bo'yicha global antiraid tekshiruvi (1 daqiqada maks 5 chaqiruv)
    group_calls = [t for t in group_call_history.get(chat_id, []) if now - t < 60]
    if len(group_calls) >= config.GROUP_MAX_CALLS_PER_MINUTE:
        bot.reply_to(message, "🛡 <b>Xavfsizlik:</b> Ushbu guruhda admin chaqiruvlari soni oshib ketdi. Spamdan himoya qilish uchun 1 daqiqa kuting.")
        return

    # 2. Foydalanuvchi shaxsiy cooldown (antispam) tekshiruvi
    if now - last_call < cooldown:
        remaining = int(cooldown - (now - last_call))
        bot.reply_to(message, f"⏳ Iltimos kuting! Siz yana <b>{remaining}</b> soniyadan so'ng adminlarni chaqira olasiz.")
        return

    user_cooldowns[(chat_id, user.id)] = now
    group_calls.append(now)
    group_call_history[chat_id] = group_calls

    # Sabab yoki qo'shimcha matnni aniqlash
    reason = ""
    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)
    if len(parts) > 1 and not parts[0].lower().startswith("@admin"):
        reason = parts[1].strip()
    elif "@admin" in text.lower():
        reason = text.replace("@admin", "").replace("@Admin", "").strip()

    # Guruh adminlarini olish
    try:
        admins = bot.get_chat_administrators(chat_id)
    except Exception as e:
        logger.error(f"Adminlarni olishda xatolik: {e}")
        bot.reply_to(
            message,
            "⚠️ Adminlar ro'yxatini olib bo'lmadi. Iltimos, botga guruhda adminlik huquqini bering!"
        )
        return

    # Faqat bot bo'lmagan adminlarni ajratish
    human_admins = [a.user for a in admins if not a.user.is_bot]

    if not human_admins:
        bot.reply_to(message, "Guruhda hech qanday inson-admin topilmadi.")
        return

    # Adminlarni formatlash
    mentions = [format_user_mention(a) for a in human_admins]
    caller_mention = format_user_mention(user)

    # Javob xabari tayyorlash
    response_lines = [
        "🚨 <b>DIQQAT, ADMINLAR!</b>",
        f"👤 <b>Chaqiruvchi:</b> {caller_mention}",
    ]

    if reason:
        response_lines.append(f"💬 <b>Sabab:</b> {escape_html(reason)}")

    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        response_lines.append(f"📌 <b>Shikoyat qilingan foydalanuvchi:</b> {format_user_mention(replied_user)}")

    response_lines.append("")
    response_lines.append("👑 <b>Adminlar:</b> " + " ".join(mentions))

    final_text = "\n".join(response_lines)

    try:
        if message.reply_to_message:
            bot.send_message(chat_id, final_text, reply_to_message_id=message.reply_to_message.message_id)
        else:
            bot.reply_to(message, final_text)
        db.log_call(chat_id, user.id, "admin_call", reason)
    except Exception as e:
        logger.error(f"Xabar yuborishda xatolik: {e}")
        bot.send_message(chat_id, final_text)

# ==================== A'ZOLARNI BELGILASH (/tag, /all, /metka, /stop) ====================

@bot.message_handler(commands=["tag", "all", "metka"])
def handle_tag_members(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user

    if message.chat.type not in ("group", "supergroup"):
        bot.reply_to(message, "ℹ️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    # Faqat adminlar bajara olishini tekshirish
    if not is_chat_admin(chat_id, user.id) and user.id not in config.ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu buyruqdan faqat guruh adminlari foydalana oladi!")
        return

    if chat_id in active_tags:
        bot.reply_to(message, "⚠️ Ushbu guruhda allaqachon belgilash jarayoni bormoqda. To'xtatish uchun: <code>/stop</code>")
        return

    # Matnni ajratish
    parts = (message.text or "").split(maxsplit=1)
    tag_message = parts[1].strip() if len(parts) > 1 else "Diqqat barcha a'zolar!"

    members = db.get_group_members(chat_id, limit=200)
    # Buyruq beruvchini ro'yxatdan chiqarish
    members = [m for m in members if m["user_id"] != user.id]

    if not members:
        bot.reply_to(
            message,
            "⚠️ Hozircha guruhda faol a'zolar saqlanmagan. "
            "A'zolar guruhda xabar yozgan sari bot ularni avtomatik ro'yxatga olib boradi!"
        )
        return

    active_tags.add(chat_id)
    bot.reply_to(
        message,
        f"📢 <b>Belgilash boshlandi!</b>\n"
        f"Jami a'zolar: {len(members)} ta."
    )

    # Alohida oqimda jo'natish
    def run_tagging():
        try:
            batch_size = config.TAG_BATCH_SIZE
            for i in range(0, len(members), batch_size):
                if chat_id not in active_tags:
                    break

                batch = members[i:i + batch_size]
                mentions = []
                for m in batch:
                    if m["username"]:
                        mentions.append(f"@{m['username']}")
                    else:
                        mentions.append(f"<a href='tg://user?id={m['user_id']}'>{escape_html(m['first_name'])}</a>")

                batch_text = f"🔔 <b>{escape_html(tag_message)}</b>\n\n" + " ".join(mentions)
                try:
                    bot.send_message(chat_id, batch_text)
                except Exception as e:
                    logger.error(f"Tag yuborishda xatolik: {e}")

                time.sleep(config.TAG_DELAY_SECONDS)

            if chat_id in active_tags:
                bot.send_message(chat_id, "✅ <b>Barcha a'zolarni belgilash yakunlandi.</b>")
        finally:
            active_tags.discard(chat_id)

    thread = threading.Thread(target=run_tagging, daemon=True)
    thread.start()

# ==================== FOYDALANUVCHILARNI KUZATISH ====================

@bot.message_handler(content_types=["text", "photo", "video", "sticker", "document", "voice"])
def track_activity(message: types.Message):
    if message.chat.type in ("group", "supergroup"):
        user = message.from_user
        if user and not user.is_bot:
            db.track_member_activity(message.chat.id, user.id, user.first_name, user.username)
            db.add_or_update_group(message.chat.id, message.chat.title, message.chat.username)

@bot.my_chat_member_handler()
def handle_my_chat_member(update: types.ChatMemberUpdated):
    """Bot guruhga qo'shilganda yoki chiqarilganda."""
    chat = update.chat
    new_status = update.new_chat_member.status
    if new_status in ("member", "administrator"):
        db.add_or_update_group(chat.id, chat.title, chat.username)
        try:
            bot.send_message(
                chat.id,
                "🎉 <b>Salom! Men Belgilovchi botman.</b>\n\n"
                "Guruhda adminlarni chaqirish uchun <code>/admin</code> yoki <code>@admin</code> deb yozing.\n"
                "A'zolarni metka qilish uchun: <code>/tag</code>\n"
                "Bot qulay ishlashi uchun unga <b>Adminlik huquqini</b> berishingiz tavsiya etiladi."
            )
        except Exception as e:
            logger.error(f"Guruhga xush kelibsiz xabarini yuborib bo'lmadi: {e}")
    elif new_status in ("left", "kicked"):
        db.deactivate_group(chat.id)

# ==================== ASOSIY ISHGA TUSHIRISH ====================

def main():
    logger.info("Starting Belgilovchi Bot (@Belgilaydibot)...")
    bot_info = bot.get_me()
    logger.info(f"Connected as @{bot_info.username} (ID: {bot_info.id})")

    # 10 ta avtomatik ichki cron vazifalarini ishga tushirish
    cron_manager.start()
    logger.info("10 ta avtomatik ichki cron vazifalari faollashtirildi")

    # Render va 24/7 monitoring uchun HTTP serverni ishga tushirish
    start_health_server_in_background(port=config.PORT, cron_manager=cron_manager)
    logger.info(f"Health-check web server started on port {config.PORT}")

    # Uzluksiz polling sikli (xatolar yuz berganda avtomatik qayta ulanadi)
    while True:
        try:
            logger.info("Bot polling boshlandi...")
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Polling xatosi: {e}. 5 soniyadan keyin qayta ulanadi...")
            time.sleep(5)

if __name__ == "__main__":
    main()
