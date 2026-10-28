#!/usr/bin/env bash
set -e

cd /root/belgilovchi-bot

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Starting Belgilovchi bot supervisor..."

while true; do
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Launching bot.py..."
  python3 bot.py || true
  echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Bot process ended. Restarting in 3 seconds..."
  sleep 3
done
