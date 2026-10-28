#!/usr/bin/env bash
echo "[$(date -u)] Starting Render Dual Keep-Alive Pinger..."
while true; do
  # 1. Belgilovchi Telegram Bot Keep-Alive
  curl -s -f "https://belgilovchi-bot.onrender.com/healthz" >/dev/null 2>&1 || true
  # 2. MUXA AI Web Platform Keep-Alive
  curl -s -f "https://muxa-ai-platform.onrender.com/healthz" >/dev/null 2>&1 || true
  sleep 300
done
