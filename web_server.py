"""
Belgilovchi Bot — Render.com va 24/7 Hosting uchun Yengil HTTP Health-Check Serveri.
UptimeRobot yoki Cron-job orqali xizmatni 24/7 faol ushlab turadi.
"""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = {
                "status": "online",
                "service": "Belgilovchi Telegram Bot (@Belgilaydibot)",
                "uptime": "24/7 active",
                "description": "Guruhlarni boshqarish va adminlarni chaqiruvchi bot"
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Jim rejimda ishlash, loglarni to'ldirmaslik
        pass

def run_health_server(port: int = 8088):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

def start_health_server_in_background(port: int = 8088):
    thread = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    thread.start()
    return thread
