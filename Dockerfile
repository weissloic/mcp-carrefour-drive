FROM --platform=linux/amd64 python:3.12-slim-bookworm

# ── System deps + Chrome ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Virtual display + VNC
    xvfb x11vnc fluxbox novnc websockify \
    # Download tools
    wget gnupg ca-certificates \
    # Chrome runtime dependencies
    fonts-liberation fonts-noto-color-emoji \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libcurl4 libdbus-1-3 \
    libdrm2 libexpat1 libgbm1 libglib2.0-0 \
    libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 \
    libudev1 libvulkan1 libx11-6 libx11-xcb1 libxcb1 \
    libxcb-dri3-0 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxkbcommon0 libxrandr2 libxss1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Google Chrome stable ──────────────────────────────────────────────────────
RUN wget -q -O /tmp/chrome.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install matching chromedriver (SeleniumBase handles version matching)
RUN python -m seleniumbase install chromedriver

# ── App source ────────────────────────────────────────────────────────────────
COPY main.py ./
COPY src/ ./src/

# ── Runtime config ────────────────────────────────────────────────────────────
ENV DISPLAY=:99
ENV BROWSER_HEADLESS=false
ENV CARREFOUR_DATA_DIR=/data

VOLUME ["/data"]
EXPOSE 6080

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
