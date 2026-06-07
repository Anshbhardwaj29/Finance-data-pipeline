import os
import requests
from core.logger import custom_logger as logger
from core.config import settings

class Notifier:
    def __init__(self):
        self.config = settings.config.get("notifications", {})
        self.enabled = self.config.get("enabled", False)
        self.provider = self.config.get("provider", "twilio_whatsapp").lower()

    def send_alert(self, message: str):
        """Dispatches a text alert based on selected notifications channel."""
        log_msg = f"[NOTIFICATION ALERT] {message}"
        logger.info(log_msg)
        
        if not self.enabled:
            return

        if self.provider == "telegram":
            self._send_telegram(message)
        elif self.provider == "twilio_sms":
            self._send_twilio(message, channel="sms")
        elif self.provider == "twilio_whatsapp":
            self._send_twilio(message, channel="whatsapp")

    def send_daily_report(self):
        """
        Sends today's Excel trading report as a file document to Telegram.
        Called automatically at end-of-day by the engine scheduler.
        """
        if not self.enabled or self.provider != "telegram":
            logger.info("Daily report sending is only supported via Telegram provider.")
            return

        import time
        date_str = time.strftime("%Y-%m-%d")
        file_path = os.path.join("logs", f"trading_report_{date_str}.xlsx")

        if not os.path.exists(file_path):
            logger.warning(f"Daily report file not found: {file_path}. No trades today?")
            # Send a text summary instead
            self.send_alert(
                f"📋 *Daily Report — {date_str}*\n\n"
                f"No completed trades were recorded today.\n"
                f"Bot is running and monitoring the market. 🔍"
            )
            return

        self._send_telegram_document(file_path, caption=f"📊 *Daily Trading Report — {date_str}*\nYour automated ATM options trade ledger for today.")

    def _send_telegram(self, message: str):
        cfg = self.config.get("telegram", {})
        token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")
        
        if not token or "YOUR_" in token or not chat_id or "YOUR_" in chat_id:
            logger.warning("Telegram notifier credentials missing or set to placeholder.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                logger.error(f"Telegram API request failed: {r.text}")
            else:
                logger.success("Telegram message dispatched successfully!")
        except Exception as e:
            logger.error(f"Failed to transmit Telegram message: {e}")

    def _send_telegram_document(self, file_path: str, caption: str = ""):
        """Sends a file/document to the configured Telegram chat."""
        cfg = self.config.get("telegram", {})
        token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")

        if not token or "YOUR_" in token or not chat_id or "YOUR_" in chat_id:
            logger.warning("Telegram notifier credentials missing or set to placeholder.")
            return

        url = f"https://api.telegram.org/bot{token}/sendDocument"

        try:
            with open(file_path, "rb") as doc:
                r = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
                    files={"document": (os.path.basename(file_path), doc)},
                    timeout=30
                )
            if r.status_code != 200:
                logger.error(f"Telegram document send failed: {r.text}")
            else:
                logger.success(f"Daily Excel report sent to Telegram successfully: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Failed to send Telegram document: {e}")

    def _send_twilio(self, message: str, channel="sms"):
        cfg = self.config.get("twilio", {})
        sid = cfg.get("account_sid")
        token = cfg.get("auth_token")
        from_num = cfg.get("from_number")
        to_num = cfg.get("to_number")

        if not sid or "YOUR_" in sid or not token or not from_num or not to_num:
            logger.warning("Twilio API credentials missing or set to placeholder in config.")
            return

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        
        # Handle WhatsApp prefixes (Twilio sandbox requires whatsapp: prefix)
        frm = f"whatsapp:{from_num}" if (channel == "whatsapp" and not from_num.startswith("whatsapp:")) else from_num
        to = f"whatsapp:{to_num}" if (channel == "whatsapp" and not to_num.startswith("whatsapp:")) else to_num
        
        payload = {"From": frm, "To": to, "Body": message}
        
        try:
            r = requests.post(url, data=payload, auth=(sid, token), timeout=5)
            if r.status_code not in [200, 201]:
                logger.error(f"Twilio API request failed: {r.text}")
            else:
                logger.success(f"Notification alert successfully dispatched via {channel.upper()}!")
        except Exception as e:
            logger.error(f"Failed to transmit Twilio alert: {e}")
