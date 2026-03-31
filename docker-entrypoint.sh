#!/usr/bin/env bash
set -e

# ── Virtual display ───────────────────────────────────────────────────────────
Xvfb :99 -screen 0 1280x900x24 -ac +extension GLX +render -noreset &

for i in $(seq 1 20); do
  xdpyinfo -display :99 >/dev/null 2>&1 && break
  sleep 0.2
done

# ── Lightweight window manager ────────────────────────────────────────────────
DISPLAY=:99 fluxbox -log /tmp/fluxbox.log &

# ── VNC server ────────────────────────────────────────────────────────────────
x11vnc -display :99 -forever -nopw -shared -quiet -bg -o /tmp/x11vnc.log

# ── noVNC web interface (port 6080) ───────────────────────────────────────────
NOVNC_PATH="$(find /usr/share/novnc /usr/share/noVNC 2>/dev/null -maxdepth 0 | head -1)"
NOVNC_PATH="${NOVNC_PATH:-/usr/share/novnc}"
websockify --web="$NOVNC_PATH" 6080 localhost:5900 --log-file=/tmp/websockify.log &

echo "[carrefour-mcp] Display prêt. noVNC → http://localhost:6080/vnc.html" >&2
echo "[carrefour-mcp] MCP via : docker exec -i carrefour-mcp python /app/main.py" >&2

# Export DISPLAY for all processes spawned later (docker exec inclus)
export DISPLAY=:99

# Garde le container en vie (le serveur MCP est lancé via docker exec par Claude)
exec tail -f /dev/null
