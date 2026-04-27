# AI Wildlife Intrusion Detection and Alert System

## Current Scope

This is a PC-based wildlife intrusion detection prototype. The main demo is:

1. Run the desktop app.
2. Upload a wildlife video or start webcam monitoring.
3. Click `Start Detection`.
4. The system runs YOLOv8 on sampled frames and draws bounding boxes around animal-like objects.
5. Each YOLO crop is classified by the existing `.h5` model.
6. If a dangerous animal is confirmed, a `DANGER` alert triggers.
7. Evidence is saved and enabled registered phone users are notified by SMS when configured.

The project does not retrain the model and does not require Raspberry Pi hardware.

## Hybrid YOLO + Classifier Detection

Pipeline:

```text
Video Frame
  -> YOLOv8 animal-like object detection
  -> crop bounding box
  -> existing .h5 species classifier
  -> final animal label
  -> dangerous animal alert logic
```

YOLO detects broad animal-like classes:

```text
bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
```

The classifier decides the final species when its confidence is high enough. Detection settings live in:

```text
data/detection_config.json
```

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

SMS is disabled by default to protect trial credits. Enable it only during final demo/testing from the Notification Settings section in the app.

The app now shows:

- SMS enabled/disabled status
- selected provider
- registered user count
- masked phone numbers
- last notification status
- notification log viewer
- alert cooldown status

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

## Evaluation Scripts

Show help for video evaluation:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py --help
```

Evaluate a video without sending SMS:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py "C:\path\to\wildlife_video.mp4" --every 30 --max-frames 60
```

Evaluate one image:

```powershell
.\.venv\Scripts\python.exe scripts\test_hybrid_on_image.py "C:\path\to\wildlife_image.jpg"
```

Outputs are saved under `assets/reports/`.

## Model Limitation

The current `.h5` model is image classification, not object detection. YOLOv8 now provides bounding boxes for broad animal-like classes, and the classifier identifies species from crops. Exact species-specific bounding boxes still require a future YOLO model trained on wildlife classes.

## Run App

```powershell
cd C:\projects\VanRakshak\wildlife_alert_system_clean
.\.venv\Scripts\python.exe app\main.py
```

## Fresh Windows PC Setup

On a brand-new Windows 10/11 PC, use:

```text
install_windows_full.bat
```

This checks or installs Git and Python 3.10, creates `.venv`, installs all Python packages, prepares YOLOv8n weights, runs verification, and creates a desktop shortcut:

```text
VanRakshak AI Wildlife Monitoring System
```

Full instructions are in:

```text
docs/FRESH_WINDOWS_SETUP.md
```

SMS remains disabled by default. `data/sms_config.json` is ignored by Git and should not be committed.

## Demo Detection Flow

1. Upload a video.
2. Click `Start Detection`.
3. The app keeps video playback smooth and runs Hybrid YOLO + Classifier checks at the selected interval.
4. The UI shows `AI Monitoring Active`, next check timing, and last checked frame/time.
5. Bounding boxes are drawn directly from Hybrid YOLO detections with labels like `Tiger 92% | YOLO: bear 71%`.
6. A danger alert triggers only after confidence, repeated detection, and cooldown rules pass.
7. The right panel separates `Current Detection` from `Latest Confirmed Alert`, so an older alert does not look like the current frame.
8. The DANGER banner shows animal, confidence, video timestamp, snapshot, notification status, and cooldown.

## Verification

```powershell
.\.venv\Scripts\python.exe scripts\test_model.py
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py --help
.\.venv\Scripts\python.exe app\main.py
```
