"""
Belgilovchi Bot — Render.com va 24/7 Hosting uchun Yengil HTTP Health-Check Serveri.
Ichki 10 ta avtomatik cron holatini ham taqdim etadi.
"""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

_global_cron_manager = None

def set_cron_manager(cron_mgr):
    global _global_cron_manager
    _global_cron_manager = cron_mgr

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            crons_count = len(_global_cron_manager.tasks) if _global_cron_manager else 10
            response = {
                "status": "online",
                "service": "Belgilovchi Telegram Bot (@Belgilaydibot)",
                "uptime": "24/7 active",
                "active_internal_crons": crons_count,
                "endpoints": {
                    "health": "/healthz",
                    "crons_status": "/crons"
                }
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8"))
        elif self.path in ("/crons", "/crons/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            crons_data = _global_cron_manager.get_status_list() if _global_cron_manager else []
            res = {
                "total_crons": len(crons_data),
                "timestamp": str(threading.current_thread().name),
                "crons": crons_data
            }
            self.wfile.write(json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Jim rejimda ishlash, loglarni to'ldirmaslik
        pass

def run_health_server(port: int = 8088):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

def start_health_server_in_background(port: int = 8088, cron_manager=None):
    if cron_manager:
        set_cron_manager(cron_manager)
    thread = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    thread.start()
    return thread
