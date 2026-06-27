import os
import time
import logging
import requests
from pathlib import Path

# Load project root .env so BOT_TOKEN / CHAT_ID work reliably even when
# the process environment does not export those variables.
try:
    root = Path(__file__).resolve().parents[2]  # .../trade-yantra
    dotenv_path = root / ".env"

    if dotenv_path.exists():
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")

            # IMPORTANT: set even if missing in the process env
            if k and v is not None and str(v).strip() != "":
                os.environ.setdefault(k, v)
except Exception as e:
    # Never hard-fail import; just log to help debugging.
    logging.getLogger("telegram_service").warning(f"[TELEGRAM] dotenv load failed: {e}")



logger = logging.getLogger("telegram_service")


def _get_env(name: str, default=None):
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return v


class TelegramService:
    def __init__(self):
        self.bot_token = _get_env("BOT_TOKEN")
        self.chat_id = _get_env("CHAT_ID")
        self.base_url = None
        if self.bot_token:
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_text_message(self, text: str):
        """Send message to configured Telegram chat.

        Required env:
          - BOT_TOKEN
          - CHAT_ID
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("[TELEGRAM] BOT_TOKEN or CHAT_ID missing. Skipping send.")
            return {"status": "skipped", "reason": "missing_env"}

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": str(self.chat_id),
            "text": text,
            "disable_web_page_preview": True,
        }

        # Basic retry for flaky networks
        last_exc = None
        for _ in range(3):
            try:
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == 200:
                    return r.json()
                last_exc = RuntimeError(f"HTTP {r.status_code}: {r.text}")
            except Exception as e:
                last_exc = e
                time.sleep(1)

        logger.error(f"[TELEGRAM] Failed to send message: {last_exc}")
        return {"status": "error", "error": str(last_exc)}


telegram_service = TelegramService()

