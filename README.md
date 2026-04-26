# AI Wildlife Intrusion Detection and Alert System

## Current Scope

This is a PC-based wildlife intrusion detection prototype. The main demo is:

1. Run the desktop app.
2. Upload a wildlife video or start webcam monitoring.
3. Click `Start Detection`.
4. The system checks frames at the selected interval.
5. If a dangerous animal is confirmed, a `DANGER` alert triggers.
6. Evidence is saved and enabled registered phone users are notified by SMS when configured.

The project does not retrain the model and does not require Raspberry Pi hardware.

## Real Phone Notifications

Real SMS is controlled by:

```text
data/sms_config.json
```

This file is ignored by Git so secrets are not committed. If it does not exist, the app creates it from:

```text
data/sms_config.example.json
```

Real SMS requires paid or free-trial credentials from an SMS provider. If `"enabled": false`, the app does not send SMS and logs notification attempts as `disabled`.

## sms_config.json Format

```json
{
  "enabled": false,
  "provider": "twilio",
  "twilio": {
    "account_sid": "",
    "auth_token": "",
    "from_number": ""
  },
  "fast2sms": {
    "api_url": "https://www.fast2sms.com/dev/bulkV2",
    "api_key": "",
    "sender_id": "",
    "route": "q"
  },
  "generic_http": {
    "api_url": "",
    "api_key": "",
    "method": "POST"
  }
}
```

## Twilio SMS Setup

1. Install requirements:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

2. Edit `data/sms_config.json`:

```json
{
  "enabled": true,
  "provider": "twilio",
  "twilio": {
    "account_sid": "your_account_sid",
    "auth_token": "your_auth_token",
    "from_number": "+1XXXXXXXXXX"
  }
}
```

For Twilio trial accounts, recipient numbers may need to be verified in Twilio.

## Fast2SMS Setup

Edit `data/sms_config.json`:

```json
{
  "enabled": true,
  "provider": "fast2sms",
  "fast2sms": {
    "api_url": "https://www.fast2sms.com/dev/bulkV2",
    "api_key": "your_fast2sms_api_key",
    "sender_id": "",
    "route": "q"
  }
}
```

The endpoint is configurable through `api_url`, so provider changes do not require code changes.

## Generic HTTP SMS Setup

Use this when another SMS gateway accepts HTTP requests.

```json
{
  "enabled": true,
  "provider": "generic_http",
  "generic_http": {
    "api_url": "https://example.com/send-sms",
    "api_key": "your_api_key",
    "method": "POST"
  }
}
```

The app sends JSON:

```json
{
  "to": "+91XXXXXXXXXX",
  "message": "Wildlife Alert...",
  "name": "Village Guard"
}
```

## Registered Users

Registered users are stored in:

```text
data/registered_users.json
```

Format:

```json
[
  {
    "name": "Village Guard",
    "phone": "+910000000000",
    "enabled": true
  }
]
```

Phone numbers must use international format, for example `+91XXXXXXXXXX`.

The app settings panel supports:

- add person name
- add phone number
- enable or disable user
- delete user
- save users
- test SMS per user

## Test SMS

Send a test SMS to all enabled registered users:

```powershell
.\.venv\Scripts\python.exe scripts\test_sms.py
```

Send a test SMS to one number:

```powershell
.\.venv\Scripts\python.exe scripts\test_sms.py --to "+91XXXXXXXXXX"
```

If SMS is disabled, this command will not send a real SMS. It will log `disabled` to:

```text
data/notification_log.json
```

## Alert SMS Message

Danger alerts send:

```text
Wildlife Alert: {animal} detected near {camera_location}. Confidence: {confidence}%. Time: {timestamp}. Move domestic animals to safety and stay indoors.
```

## SMS Spam Prevention

SMS is only attempted when a real `DANGER` alert is triggered. The existing confidence threshold, repeated detection rule, and alert cooldown must pass first, so SMS is not sent on every frame.

## Evidence and Metrics

For each danger alert, the system records:

- video filename
- detection video timestamp
- detection frame number
- AI processing time in milliseconds
- alert decision time in milliseconds
- current playback FPS
- snapshot path
- notification status

## Model Limitation

The current `.h5` model is image classification, not object detection. It identifies the main animal in a frame but cannot provide exact bounding boxes. The app shows a full-frame red border during danger state. Exact animal location requires a future YOLO/object-detection upgrade.

## Run App

```powershell
cd C:\projects\VanRakshak\wildlife_alert_system_clean
.\.venv\Scripts\python.exe app\main.py
```

## Verification

```powershell
.\.venv\Scripts\python.exe scripts\test_model.py
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe app\main.py
```
