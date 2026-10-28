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
user_cooldowns = {}     # (chat_id, user_id) -> timestamp
active_tags = set()     # chat_ids currently running /tag process

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

@bot.message_handler(commands=["start"])
def handle_start(message: types.Message):
    user = message.from_user
    db.add_or_update_user(user.id, user.first_name, user.username)

    if message.chat.type in ("group", "supergroup"):
        db.add_or_update_group(message.chat.id, message.chat.title, message.chat.username)
        bot.reply_to(
            message,
            "👋 <b>Belgilovchi bot guruhda faol!</b>\n\n"
            "Adminlarni chaqirish uchun <code>/admin</code> yoki <code>@admin</code> deb yozing.\n"
            "Buyruqlar ro'yxati: <code>/help</code>"
        )
        return

    # Shaxsiy chatda xush kelibsiz xabari
    markup = types.InlineKeyboardMarkup(row_width=1)
    bot_info = bot.get_me()
    btn_add = types.InlineKeyboardButton(
        "➕ Guruhga qo'shish",
        url=f"https://t.me/{bot_info.username}?startgroup=true"
    )
    btn_help = types.InlineKeyboardButton("📖 Qo'llanma va Buyruqlar", callback_data="help_menu")
    btn_stats = types.InlineKeyboardButton("📊 Bot Statistikasi", callback_data="bot_stats")
    markup.add(btn_add, btn_help, btn_stats)

    text = (
        f"👋 <b>Assalomu alaykum, {escape_html(user.first_name)}!</b>\n\n"
        f"⚡ Men <b>Belgilovchi bot</b> (@{bot_info.username}) — guruhlarda adminlarni va a'zolarni "
        f"bir zumda chaqirib (metka / tag qilib) beruvchi professional botman.\n\n"
        f"👑 <b>Guruhda:</b>\n"
        f"• <code>/admin [sabab]</code> — Barcha adminlarni zudlik bilan chaqiradi.\n"
        f"• <code>@admin [sabab]</code> — Xabarga javob berib yozilsa, qoidabuzarlik haqida xabar beradi.\n"
        f"• <code>/tag [xabar]</code> — Guruh a'zolariga e'lon yuborish (faqat adminlar uchun).\n"
        f"• <code>/stop</code> — Belgilash jarayonini to'xtatish.\n\n"
        f"🚀 <b>Ishlatish:</b> Quyidagi tugma orqali botni guruhingizga qo'shing va adminlik bering!"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["help"])
def handle_help(message: types.Message):
    help_text = (
        "📖 <b>Belgilovchi bot bo'yicha qo'llanma:</b>\n\n"
        "1️⃣ <b>Adminlarni chaqirish:</b>\n"
        "• <code>/admin</code> yoki <code>@admin</code> — guruhdagi barcha inson adminlarga xabar beradi.\n"
        "• Xabarga reply qilib <code>/admin</code> yozsangiz, o'sha xabar ham adminlarga ko'rsatiladi.\n\n"
        "2️⃣ <b>A'zolarni metka qilish (Faqat adminlar uchun):</b>\n"
        "• <code>/tag [e'lon matni]</code> — Guruh a'zolarini navbat bilan belgilab chiqadi.\n"
        "• <code>/all [matn]</code> — <code>/tag</code> bilan bir xil ishlaydi.\n"
        "• <code>/stop</code> — Faol belgilash jarayonini to'xtatadi.\n\n"
        "3️⃣ <b>Muhim eslatma:</b>\n"
        "Bot xabarlarni to'liq ko'ra olishi va hamma adminlarni tez chaqirishi uchun "
        "unga guruhda <b>Admin huquqini</b> berishingiz tavsiya etiladi."
    )
    bot.reply_to(message, help_text)

# ==================== ADMIN CHAQIRISH (/admin, @admin, /admins) ====================

@bot.message_handler(commands=["admin", "admins", "calladmin", "report"])
def handle_admin_call_command(message: types.Message):
    trigger_admin_call(message)

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and m.text and "@admin" in m.text.lower())
def handle_admin_mention(message: types.Message):
    trigger_admin_call(message)

def trigger_admin_call(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user

    if message.chat.type not in ("group", "supergroup"):
        bot.reply_to(message, "ℹ️ Bu buyruq faqat guruhlarda ishlaydi. Botni guruhga qo'shing!")
        return

    # Guruh va a'zoni bazada saqlash
    db.add_or_update_group(chat_id, message.chat.title, message.chat.username)
    db.track_member_activity(chat_id, user.id, user.first_name, user.username)

    # Cooldown (antispam) tekshirish
    now = time.time()
    last_call = user_cooldowns.get((chat_id, user.id), 0)
    cooldown = config.ADMIN_CALL_COOLDOWN

    if now - last_call < cooldown:
        remaining = int(cooldown - (now - last_call))
        bot.reply_to(message, f"⏳ Iltimos kuting! Siz yana <b>{remaining}</b> soniyadan so'ng adminlarni chaqira olasiz.")
        return

    user_cooldowns[(chat_id, user.id)] = now

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
        f"Jami a'zolar: {len(members)} ta.\n"
        f"To'xtatish uchun: <code>/stop</code>"
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

@bot.message_handler(commands=["stop", "cancel"])
def handle_stop_tag(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user

    if message.chat.type not in ("group", "supergroup"):
        return

    if not is_chat_admin(chat_id, user.id) and user.id not in config.ADMIN_IDS:
        bot.reply_to(message, "⛔ Faqat adminlar to'xtatishi mumkin!")
        return

    if chat_id in active_tags:
        active_tags.discard(chat_id)
        bot.reply_to(message, "🛑 <b>Belgilash jarayoni muvaffaqiyatli to'xtatildi.</b>")
    else:
        bot.reply_to(message, "Hozirda faol belgilash jarayoni mavjud emas.")

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

# ==================== ADMIN BUYRUQLARI VA STATISTIKA ====================

@bot.message_handler(commands=["stats"])
def handle_stats_command(message: types.Message):
    user = message.from_user
    if user.id not in config.ADMIN_IDS:
        return

    stats = db.get_stats()
    text = (
        "📊 <b>Belgilovchi bot statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar soni: <b>{stats['total_users']}</b> ta\n"
        f"👥 Faol guruhlar soni: <b>{stats['total_groups']}</b> ta\n"
        f"📝 Ro'yxatga olingan guruh a'zolari: <b>{stats['total_tracked_members']}</b> ta\n"
        f"🚨 Jami admin chaqiruvlari: <b>{stats['total_calls']}</b> ta\n"
        f"⚡ Holati: <b>24/7 Onlayn</b>"
    )
    bot.reply_to(message, text)

# ==================== CALLBACK QUERY LAR ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: types.CallbackQuery):
    if call.data == "help_menu":
        help_text = (
            "📖 <b>Buyruqlar:</b>\n\n"
            "• <code>/admin [sabab]</code> — Barcha adminlarni chaqiradi.\n"
            "• <code>@admin</code> — Xabarga javob orqali adminni chaqirish.\n"
            "• <code>/tag [matn]</code> — Guruh a'zolariga e'lon yuborish (adminlar uchun).\n"
            "• <code>/stop</code> — Belgilashni to'xtatish.\n\n"
            "Botni guruhga qo'shing va adminlik huquqini bering!"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, help_text)
    elif call.data == "bot_stats":
        stats = db.get_stats()
        text = (
            f"📊 <b>Bot ko'rsatkichlari:</b>\n\n"
            f"• Faol guruhlar: <b>{stats['total_groups']}</b> ta\n"
            f"• Foydalanuvchilar: <b>{stats['total_users']}</b> ta\n"
            f"• Admin chaqiruvlari: <b>{stats['total_calls']}</b> marta\n"
            f"• Server: <b>24/7 Faol</b>"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text)

# ==================== ASOSIY ISHGA TUSHIRISH ====================

def main():
    logger.info("Starting Belgilovchi Bot (@Belgilaydibot)...")
    bot_info = bot.get_me()
    logger.info(f"Connected as @{bot_info.username} (ID: {bot_info.id})")

    # Render va 24/7 monitoring uchun HTTP serverni ishga tushirish
    start_health_server_in_background(port=config.PORT)
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
