# ── Runtime ────────────────────────────────────────────────────
FROM python:3.12-alpine

WORKDIR /app

# Install dependencies directly in the runtime image
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY bot.py .

# Create non-root user for security
RUN addgroup -S bot && adduser -S -G bot bot && chown -R bot:bot /app

USER bot

CMD ["python", "bot.py"]
