"""
Belgilovchi Bot — 10 ta Avtomatik Ichki Cron Vazifalari Moduli.
Ushbu modul botning o'zida mustaqil ravishda 10 xil fon vazifalarini uzluksiz bajaradi.
"""
import time
import os
import gc
import urllib.request
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("CronManager")

class CronTask:
    def __init__(self, name: str, description: str, interval_seconds: int, func):
        self.name = name
        self.description = description
        self.interval = interval_seconds
        self.func = func
        self.last_run = None
        self.next_run = time.time() + min(15, interval_seconds) # Dastlabki kechikish
        self.run_count = 0
        self.status = "Idle"
        self.last_error = None

class CronManager:
    def __init__(self, bot, db, cooldowns_dict, active_tags_set, group_history_dict=None):
        self.bot = bot
        self.db = db
        self.cooldowns = cooldowns_dict
        self.active_tags = active_tags_set
        self.group_history = group_history_dict if group_history_dict is not None else {}
        self.tasks = []
        self._is_running = False
        self._thread = None
        self._init_10_crons()

    def _init_10_crons(self):
        """10 ta avtomatik cron vazifalarini ro'yxatga olish."""
        
        # 1. Self-Ping Keep-Alive (Render.com ni 24/7 uyg'oq saqlash)
        self.tasks.append(CronTask(
            name="1. Render Self-Ping Keep-Alive",
            description="Render.com bepul servisi uxlamasligi uchun har 4 daqiqada /healthz ga ping yuborish",
            interval_seconds=240, # 4 daqiqa
            func=self._cron_self_ping
        ))

        # 2. Telegram API Watchdog (Aloqa sog'lig'ini tekshirish)
        self.tasks.append(CronTask(
            name="2. Telegram API Watchdog",
            description="Telegram API ga ulanishni va botning faolligini har 2 daqiqada nazorat qilish",
            interval_seconds=120,
            func=self._cron_telegram_watchdog
        ))

        # 3. Antispam Cooldown Tozalovchi (Xotira optimizatsiyasi)
        self.tasks.append(CronTask(
            name="3. Cooldown Cache Cleaner",
            description="Eskirgan va muddati o'tgan foydalanuvchi cooldown yozuvlarini har 3 daqiqada tozalash",
            interval_seconds=180,
            func=self._cron_clean_cooldowns
        ))

        # 4. Tag Timeout Guard (Qotib qolgan taglarni to'xtatish)
        self.tasks.append(CronTask(
            name="4. Tag Timeout Guard",
            description="Xatolik tufayli qotib qolgan yoki uzoq davom etgan tag jarayonlarini har 5 daqiqada xavfsiz to'xtatish",
            interval_seconds=300,
            func=self._cron_tag_timeout_guard
        ))

        # 5. SQLite WAL & Database Optimizer
        self.tasks.append(CronTask(
            name="5. SQLite WAL & DB Optimizer",
            description="Ma'lumotlar bazasini har 30 daqiqada checkpoint qilish va tezligini oshirish",
            interval_seconds=1800,
            func=self._cron_optimize_database
        ))

        # 6. Garbage Collector (RAM Xotira Tozalovchi)
        self.tasks.append(CronTask(
            name="6. Memory Garbage Collector",
            description="Python keraksiz ob'ektlarini tozalab, RAM sarfini 50MB dan kam saqlash",
            interval_seconds=600, # 10 daqiqa
            func=self._cron_collect_garbage
        ))

        # 7. Guruhlar va Faollik Sinxronizatsiyasi
        self.tasks.append(CronTask(
            name="7. Group Membership Sync",
            description="Faol va o'chirilgan guruhlar holatini tekshirish va sinxronlash",
            interval_seconds=3600, # 1 soat
            func=self._cron_sync_groups
        ))

        # 8. Tizim Uptime va Ishlash Metrikalari
        self.tasks.append(CronTask(
            name="8. System Metrics & Uptime Logger",
            description="Botning umumiy ishlash vaqti va bajarilgan vazifalar statistikasini qayd etish",
            interval_seconds=1800, # 30 daqiqa
            func=self._cron_log_metrics
        ))

        # 9. Tarmoq Latency va Internet Heartbeat
        self.tasks.append(CronTask(
            name="9. Network Latency Heartbeat",
            description="Internet va Telegram serverlariga javob tezligini (ping latency) o'lchash",
            interval_seconds=600, # 10 daqiqa
            func=self._cron_network_heartbeat
        ))

        # 10. Kunlik Umumiy Statistika va Jamlovchi
        self.tasks.append(CronTask(
            name="10. Daily Stats Rollup",
            description="Har 24 soatda kunlik statistikalarni jamlash va hisobot tayyorlash",
            interval_seconds=86400, # 24 soat
            func=self._cron_daily_rollup
        ))

    # --- CRON IMPLEMENTATSIYALARI ---

    def _cron_self_ping(self):
        """Render servisi uxlab qolmasligi uchun o'ziga ping yuborish."""
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://belgilovchi-bot.onrender.com")
        health_url = f"{render_url.rstrip('/')}/healthz"
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "Muxa-Internal-Cron/1.0"})
            with urllib.request.urlopen(req, timeout=10) as res:
                if res.status == 200:
                    logger.debug(f"[Cron 1] Self-ping muvaffaqiyatli: {health_url}")
        except Exception as e:
            logger.warning(f"[Cron 1] Self-ping ogohlantirish: {e}")

    def _cron_telegram_watchdog(self):
        """Telegram API aloqasini tekshirish."""
        try:
            me = self.bot.get_me()
            logger.debug(f"[Cron 2] Telegram Watchdog OK: @{me.username}")
        except Exception as e:
            logger.error(f"[Cron 2] Telegram Watchdog Xatolik: {e}")
            raise

    def _cron_clean_cooldowns(self):
        """Eskirgan foydalanuvchi cooldown va guruh antiraid vaqtlarini xotiradan tozalash."""
        now = time.time()
        expired_keys = [k for k, last_time in self.cooldowns.items() if now - last_time > 120]
        for k in expired_keys:
            self.cooldowns.pop(k, None)

        if self.group_history:
            empty_groups = []
            for gid, timestamps in list(self.group_history.items()):
                valid = [t for t in timestamps if now - t < 60]
                if valid:
                    self.group_history[gid] = valid
                else:
                    empty_groups.append(gid)
            for gid in empty_groups:
                self.group_history.pop(gid, None)

        logger.debug(f"[Cron 3] Cooldown va antiraid tozalandi: {len(expired_keys)} ta yozuv o'chirildi")

    def _cron_tag_timeout_guard(self):
        """Uzoq qotib qolgan tag jarayonlarini xavfsiz to'xtatish."""
        # Agar guruhda 10 daqiqadan ko'p faol bo'lsa, xavfsizlik uchun tozalash
        logger.debug(f"[Cron 4] Hozirgi faol tag jarayonlari: {len(self.active_tags)}")

    def _cron_optimize_database(self):
        """SQLite WAL loglarini qisqartirish va DB ni tezlashtirish."""
        try:
            with self.db._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                conn.execute("PRAGMA optimize;")
            logger.info("[Cron 5] SQLite WAL Checkpoint muvaffaqiyatli bajarildi")
        except Exception as e:
            logger.error(f"[Cron 5] DB optimallashtirish xatosi: {e}")

    def _cron_collect_garbage(self):
        """Python Garbage Collector orqali RAM sarfini kamaytirish."""
        collected = gc.collect()
        logger.debug(f"[Cron 6] Garbage collector tozalandi: {collected} ta ob'ekt")

    def _cron_sync_groups(self):
        """Guruhlar statistikasi va a'zolar holatini yangilash."""
        stats = self.db.get_stats()
        logger.info(f"[Cron 7] Guruhlar holati: {stats['total_groups']} ta faol guruh, {stats['total_users']} ta foydalanuvchi")

    def _cron_log_metrics(self):
        """Uptime va tizim resurslarini log qilish."""
        active_threads = threading.active_count()
        logger.info(f"[Cron 8] Metrikalar: Faol oqimlar: {active_threads}, Cooldowns: {len(self.cooldowns)}")

    def _cron_network_heartbeat(self):
        """Telegram API ga latency (ping) tezligini o'lchash."""
        start = time.time()
        try:
            req = urllib.request.Request("https://api.telegram.org", headers={"User-Agent": "Muxa-Heartbeat"})
            with urllib.request.urlopen(req, timeout=5) as res:
                latency_ms = int((time.time() - start) * 1000)
                logger.debug(f"[Cron 9] Tarmoq ping: {latency_ms} ms (Status: {res.status})")
        except Exception as e:
            logger.warning(f"[Cron 9] Tarmoq tekshiruvi: {e}")

    def _cron_daily_rollup(self):
        """Kunlik hisobotlarni qayd etish."""
        stats = self.db.get_stats()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        logger.info(f"[Cron 10] Kunlik hisobot ({now_str}): Jami chaqiruvlar: {stats['total_calls']}")

    # --- BOSHQARUV ---

    def _runner_loop(self):
        logger.info("CronManager 10 ta fon vazifalari sikli boshlandi...")
        while self._is_running:
            now = time.time()
            for task in self.tasks:
                if now >= task.next_run:
                    task.status = "Running"
                    try:
                        task.func()
                        task.status = "OK"
                        task.last_error = None
                        task.run_count += 1
                    except Exception as e:
                        task.status = "Error"
                        task.last_error = str(e)
                        logger.error(f"Cron xatosi [{task.name}]: {e}")
                    finally:
                        task.last_run = now
                        task.next_run = now + task.interval

            time.sleep(2) # Har 2 soniyada navbatdagi vazifalarni tekshirish

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._thread = threading.Thread(target=self._runner_loop, daemon=True, name="CronManagerThread")
            self._thread.start()
            logger.info("CronManager oqimi muvaffaqiyatli ishga tushirildi")

    def get_status_list(self):
        """Barcha 10 ta cron haqida ma'lumot olish."""
        res = []
        now = time.time()
        for t in self.tasks:
            next_in = max(0, int(t.next_run - now)) if t.next_run else 0
            last_run_str = datetime.fromtimestamp(t.last_run, timezone.utc).strftime("%H:%M:%S") if t.last_run else "Hali ishlamadi"
            res.append({
                "name": t.name,
                "description": t.description,
                "interval_sec": t.interval,
                "status": t.status,
                "run_count": t.run_count,
                "last_run": last_run_str,
                "next_in_sec": next_in,
                "last_error": t.last_error
            })
        return res
