from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.notification_service import NotificationService, is_valid_phone, mask_phone


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test SMS using data/sms_config.json")
    parser.add_argument("--to", help="Send a test SMS to one phone number, e.g. +91XXXXXXXXXX")
    args = parser.parse_args()

    service = NotificationService()
    debug = service.debug_sms_config_summary()
    twilio = debug["twilio"]
    print("[CONFIG]")
    print(f"  path: {debug['config_path']}")
    print(f"  exists: {debug['config_exists']}")
    print(f"  enabled: {debug['enabled']} ({debug['enabled_type']})")
    print(f"  provider: {debug['provider']}")
    print(f"  twilio.account_sid: {twilio['account_sid']}")
    print(f"  twilio.auth_token: {twilio['auth_token']}")
    print(f"  twilio.from_number: {twilio['from_number']}")

    if args.to:
        if not is_valid_phone(args.to):
            print(f"[FAILED] Invalid phone number: {mask_phone(args.to)}")
            return 1
        users = [{"name": "Manual Test", "phone": args.to, "enabled": True}]
    else:
        users = [user for user in service.load_registered_users() if bool(user.get("enabled", True))]

    if not users:
        print("[FAILED] No enabled registered users found.")
        return 1

    exit_code = 0
    for user in users:
        result = service.send_test_sms(user)
        status = result.get("status", "unknown")
        error = result.get("error")
        print(f"[{str(status).upper()}] {result.get('user_name')} {mask_phone(result.get('phone'))} provider={result.get('provider')}")
        if error:
            print(f"  error: {error}")
        if status not in {"sent", "disabled"}:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
