from __future__ import annotations

import shutil
import re
from typing import Any

from app.utils.paths import (
    REPORTS_DIR,
    NOTIFICATION_LOG_PATH,
    REGISTERED_USERS_PATH,
    SMS_CONFIG_EXAMPLE_PATH,
    SMS_CONFIG_PATH,
    load_json,
    save_json,
)
from app.utils.time_utils import iso_timestamp


DEFAULT_SMS_CONFIG = {
    "enabled": False,
    "provider": "twilio",
    "twilio": {
        "account_sid": "",
        "auth_token": "",
        "from_number": "",
    },
    "fast2sms": {
        "api_url": "https://www.fast2sms.com/dev/bulkV2",
        "api_key": "",
        "sender_id": "",
        "route": "q",
    },
    "generic_http": {
        "api_url": "",
        "api_key": "",
        "method": "POST",
    },
}

DEFAULT_REGISTERED_USERS = [
    {"name": "Village Guard", "phone": "+910000000000", "enabled": True},
]

PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_PATTERN.match(str(phone).strip()))


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def mask_value(value: Any, visible: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    if len(text) <= visible * 2:
        return "*" * len(text)
    return f"{text[:visible]}...{text[-visible:]}"


def mask_phone(phone: Any) -> str:
    text = str(phone or "").strip()
    if len(text) <= 5:
        return mask_value(text, 1)
    if len(text) > 8:
        return f"{text[:3]}{'*' * max(2, len(text) - 7)}{text[-4:]}"
    return f"{text[:3]}...{text[-2:]}"


class NotificationService:
    def __init__(self) -> None:
        self.registered_users_path = REGISTERED_USERS_PATH
        self.notification_log_path = NOTIFICATION_LOG_PATH
        self.sms_config_path = SMS_CONFIG_PATH
        self.sms_config_example_path = SMS_CONFIG_EXAMPLE_PATH
        self.ensure_files()

    def ensure_files(self) -> None:
        if not self.sms_config_example_path.exists():
            save_json(self.sms_config_example_path, DEFAULT_SMS_CONFIG)
        if not self.sms_config_path.exists():
            if self.sms_config_example_path.exists():
                shutil.copyfile(self.sms_config_example_path, self.sms_config_path)
            config = load_json(self.sms_config_path, DEFAULT_SMS_CONFIG)
            if not isinstance(config, dict):
                config = DEFAULT_SMS_CONFIG.copy()
            config["enabled"] = False
            save_json(self.sms_config_path, config)
        if not self.registered_users_path.exists():
            save_json(self.registered_users_path, DEFAULT_REGISTERED_USERS)
        if not self.notification_log_path.exists():
            save_json(self.notification_log_path, [])

    def load_sms_config(self) -> dict[str, Any]:
        loaded = load_json(self.sms_config_path, {})
        return self._merge_sms_config(loaded if isinstance(loaded, dict) else {})

    def debug_sms_config_summary(self) -> dict[str, Any]:
        config = self.load_sms_config()
        twilio_config = config.get("twilio", {}) if isinstance(config.get("twilio"), dict) else {}
        return {
            "config_path": str(self.sms_config_path.resolve()),
            "config_exists": self.sms_config_path.exists(),
            "enabled": config.get("enabled"),
            "enabled_type": type(config.get("enabled")).__name__,
            "provider": str(config.get("provider", "twilio")),
            "twilio": {
                "account_sid": mask_value(twilio_config.get("account_sid")),
                "auth_token": mask_value(twilio_config.get("auth_token")),
                "from_number": mask_phone(twilio_config.get("from_number")),
            },
        }

    def sms_status(self) -> dict[str, Any]:
        config = self.load_sms_config()
        users = [user for user in self.load_registered_users() if bool(user.get("enabled", True))]
        last = self.last_notification()
        return {
            "enabled": bool(config.get("enabled")),
            "provider": str(config.get("provider", "twilio")),
            "registered_users_count": len(users),
            "last_status": str(last.get("status", "--")) if last else "--",
            "last_error": last.get("error") if last else None,
            "last_timestamp": last.get("timestamp") if last else None,
        }

    def save_sms_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        config = self.load_sms_config()
        if "enabled" in updates:
            config["enabled"] = parse_bool(updates["enabled"])
        if "provider" in updates:
            provider = str(updates["provider"]).strip().casefold().replace(" ", "_")
            if provider not in {"twilio", "fast2sms", "generic_http"}:
                raise ValueError(f"Unsupported SMS provider: {updates['provider']}")
            config["provider"] = provider
        save_json(self.sms_config_path, config)
        return self.load_sms_config()

    def last_notification(self) -> dict[str, Any] | None:
        logs = load_json(self.notification_log_path, [])
        if isinstance(logs, list) and logs:
            last = logs[-1]
            return last if isinstance(last, dict) else None
        return None

    def load_registered_users(self) -> list[dict[str, Any]]:
        users = load_json(self.registered_users_path, DEFAULT_REGISTERED_USERS)
        return users if isinstance(users, list) else []

    def users_with_last_status(self) -> list[dict[str, Any]]:
        logs = self.load_notification_log()
        last_by_phone: dict[str, dict[str, Any]] = {}
        for row in logs:
            phone = str(row.get("phone", ""))
            if phone:
                last_by_phone[phone] = row
        users = []
        for user in self.load_registered_users():
            row = dict(user)
            last = last_by_phone.get(str(user.get("phone", "")), {})
            row["last_status"] = last.get("status", "--")
            row["last_timestamp"] = last.get("timestamp", "")
            row["masked_phone"] = mask_phone(row.get("phone", ""))
            users.append(row)
        return users

    def load_notification_log(self) -> list[dict[str, Any]]:
        logs = load_json(self.notification_log_path, [])
        return logs if isinstance(logs, list) else []

    def clear_notification_log(self) -> None:
        save_json(self.notification_log_path, [])

    def export_notification_log(self) -> str:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / "notification_log_export.json"
        save_json(path, self.load_notification_log())
        return str(path)

    def save_registered_users(self, users: list[dict[str, Any]]) -> None:
        cleaned: list[dict[str, Any]] = []
        for user in users:
            if not isinstance(user, dict):
                continue
            name = str(user.get("name", "")).strip()
            phone = str(user.get("phone", "")).strip()
            if not name:
                raise ValueError("Registered user name is required")
            if not is_valid_phone(phone):
                raise ValueError(f"Invalid phone number for {name}: {phone}")
            cleaned.append({"name": name, "phone": phone, "enabled": bool(user.get("enabled", True))})
        save_json(self.registered_users_path, cleaned)

    def send_alert_to_registered_users(self, alert_event: dict[str, Any]) -> list[dict[str, Any]]:
        users = [user for user in self.load_registered_users() if bool(user.get("enabled", True))]
        message = self.message_for_event(alert_event)
        results: list[dict[str, Any]] = []
        if not users:
            return results

        config = self.load_sms_config()
        provider = str(config.get("provider", "twilio")).strip().casefold()
        if not parse_bool(config.get("enabled")):
            for user in users:
                results.append(self._log_notification(user, message, provider, "disabled", "Real SMS disabled. Enable data/sms_config.json."))
            return results

        for user in users:
            if provider == "twilio":
                results.append(self.send_sms_twilio(user, message, config))
            elif provider == "fast2sms":
                results.append(self.send_sms_fast2sms(user, message, config))
            elif provider in {"generic", "generic_http"}:
                results.append(self.send_sms_generic_http(user, message, config))
            else:
                results.append(self._log_notification(user, message, provider, "failed", f"Unsupported SMS provider: {provider}"))
        return results

    def send_test_sms(self, user: dict[str, Any]) -> dict[str, Any]:
        message = "Wildlife Alert test SMS. If you received this, phone notifications are configured."
        config = self.load_sms_config()
        provider = str(config.get("provider", "twilio")).strip().casefold()
        if not parse_bool(config.get("enabled")):
            return self._log_notification(user, message, provider, "disabled", "Real SMS disabled. Enable data/sms_config.json.")
        if provider == "twilio":
            return self.send_sms_twilio(user, message, config)
        if provider == "fast2sms":
            return self.send_sms_fast2sms(user, message, config)
        if provider in {"generic", "generic_http"}:
            return self.send_sms_generic_http(user, message, config)
        return self._log_notification(user, message, provider, "failed", f"Unsupported SMS provider: {provider}")

    def send_sms_twilio(
        self,
        user: dict[str, Any],
        message: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or self.load_sms_config()
        twilio_config = config.get("twilio", {}) if isinstance(config.get("twilio"), dict) else {}
        account_sid = str(twilio_config.get("account_sid", "")).strip()
        auth_token = str(twilio_config.get("auth_token", "")).strip()
        from_number = str(twilio_config.get("from_number", "")).strip()
        if not account_sid or not auth_token or not from_number:
            return self._log_notification(user, message, "twilio", "failed", "Twilio account_sid, auth_token, and from_number are required.")
        try:
            from twilio.rest import Client
        except ImportError:
            return self._log_notification(user, message, "twilio", "failed", "Twilio package missing. Run: pip install twilio")

        try:
            client = Client(account_sid, auth_token)
            sent = client.messages.create(body=message, from_=from_number, to=str(user.get("phone", "")))
            return self._log_notification(user, message, "twilio", "sent", None, {"message_sid": getattr(sent, "sid", "")})
        except Exception as exc:
            error = self._mask_error(str(exc), account_sid, auth_token, from_number, user.get("phone", ""))
            return self._log_notification(user, message, "twilio", "failed", error)

    def send_sms_fast2sms(
        self,
        user: dict[str, Any],
        message: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or self.load_sms_config()
        fast_config = config.get("fast2sms", {}) if isinstance(config.get("fast2sms"), dict) else {}
        api_key = str(fast_config.get("api_key", "")).strip()
        api_url = str(fast_config.get("api_url", "https://www.fast2sms.com/dev/bulkV2")).strip()
        sender_id = str(fast_config.get("sender_id", "")).strip()
        route = str(fast_config.get("route", "q")).strip() or "q"
        if not api_key:
            return self._log_notification(user, message, "fast2sms", "failed", "Fast2SMS api_key is required.")

        payload = {
            "route": route,
            "message": message,
            "language": "english",
            "flash": 0,
            "numbers": self._fast2sms_number(user),
        }
        if sender_id:
            payload["sender_id"] = sender_id

        try:
            import requests

            response = requests.post(
                api_url,
                json=payload,
                headers={"authorization": api_key, "Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return self._log_notification(user, message, "fast2sms", "sent", None, {"response": response.text[:300]})
        except Exception as exc:
            return self._log_notification(user, message, "fast2sms", "failed", str(exc))

    def send_sms_generic_http(
        self,
        user: dict[str, Any],
        message: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or self.load_sms_config()
        generic_config = config.get("generic_http", {}) if isinstance(config.get("generic_http"), dict) else {}
        api_url = str(generic_config.get("api_url", "")).strip()
        api_key = str(generic_config.get("api_key", "")).strip()
        method = str(generic_config.get("method", "POST")).strip().upper() or "POST"
        if not api_url:
            return self._log_notification(user, message, "generic_http", "failed", "generic_http.api_url is required.")

        payload = {"to": str(user.get("phone", "")), "message": message, "name": str(user.get("name", ""))}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            import requests

            if method == "GET":
                response = requests.get(api_url, params=payload, headers=headers, timeout=10)
            else:
                response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return self._log_notification(user, message, "generic_http", "sent", None, {"response": response.text[:300]})
        except Exception as exc:
            return self._log_notification(user, message, "generic_http", "failed", str(exc))

    def message_for_event(self, alert_event: dict[str, Any]) -> str:
        if alert_event.get("message"):
            return str(alert_event["message"])
        confidence_percent = round(float(alert_event.get("confidence", 0.0)) * 100)
        return (
            f"Wildlife Alert: {alert_event.get('animal', 'Unknown')} detected near "
            f"{alert_event.get('camera_location', 'camera')}. Confidence: {confidence_percent}%. "
            f"Time: {alert_event.get('timestamp', '')}. Move domestic animals to safety and stay indoors."
        )

    def _merge_sms_config(self, loaded: dict[str, Any]) -> dict[str, Any]:
        config = {
            "enabled": parse_bool(loaded.get("enabled", DEFAULT_SMS_CONFIG["enabled"])),
            "provider": str(loaded.get("provider", DEFAULT_SMS_CONFIG["provider"])),
            "twilio": DEFAULT_SMS_CONFIG["twilio"].copy(),
            "fast2sms": DEFAULT_SMS_CONFIG["fast2sms"].copy(),
            "generic_http": DEFAULT_SMS_CONFIG["generic_http"].copy(),
        }
        for key in ("twilio", "fast2sms", "generic_http"):
            value = loaded.get(key, {})
            if isinstance(value, dict):
                config[key].update(value)

        # Backward compatibility for the previous flat sms_config format.
        if loaded.get("account_sid"):
            config["twilio"]["account_sid"] = loaded.get("account_sid", "")
        if loaded.get("auth_token"):
            config["twilio"]["auth_token"] = loaded.get("auth_token", "")
        if loaded.get("from_number"):
            config["twilio"]["from_number"] = loaded.get("from_number", "")
        if loaded.get("generic_api_url"):
            config["generic_http"]["api_url"] = loaded.get("generic_api_url", "")
        if loaded.get("generic_api_key"):
            config["generic_http"]["api_key"] = loaded.get("generic_api_key", "")
        return config

    def _fast2sms_number(self, user: dict[str, Any]) -> str:
        phone = str(user.get("phone", "")).strip()
        if phone.startswith("+91"):
            return phone[3:]
        return phone.lstrip("+")

    def _mask_error(self, error: str, *sensitive_values: Any) -> str:
        sanitized = error
        for value in sensitive_values:
            text = str(value or "").strip()
            if text:
                sanitized = sanitized.replace(text, mask_value(text))
        return sanitized

    def _log_notification(
        self,
        user: dict[str, Any],
        message: str,
        provider: str,
        status: str,
        error: str | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "timestamp": iso_timestamp(),
            "user_name": str(user.get("name", "")),
            "phone": str(user.get("phone", "")),
            "message": message,
            "provider": provider,
            "status": status,
            "error": error,
        }
        if extra:
            row.update(extra)
        logs = load_json(self.notification_log_path, [])
        if not isinstance(logs, list):
            logs = []
        logs.append(row)
        save_json(self.notification_log_path, logs)
        print(f"[SMS {provider.upper()}] {status}: {message}")
        return row
