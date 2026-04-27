# Setup And Demo Guide

## Install

```powershell
cd C:\projects\VanRakshak\wildlife_alert_system_clean
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Verify

```powershell
.\.venv\Scripts\python.exe scripts\test_model.py
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py --help
```

## Run UI

```powershell
.\.venv\Scripts\python.exe app\main.py
```

## Demo Flow

1. Click upload video.
2. Select a wildlife video.
3. Confirm the first frame is shown and the video does not auto-play.
4. Click Start Detection.
5. Watch bounding boxes, labels, confidence, processing time, frame number, and timestamp.
6. When a dangerous animal is repeatedly detected, the DANGER alert saves a snapshot and logs the event.
7. Export the report from the sidebar.

## SMS

Real SMS is disabled by default in `data/sms_config.json`. Keep this file local and never commit it. To test real SMS later, enable the local config and run:

```powershell
.\.venv\Scripts\python.exe scripts\test_sms.py --to "+91XXXXXXXXXX"
```

In the UI, use Notification Settings to:

- keep SMS disabled during normal testing
- enable SMS only for final demo
- choose Twilio, Fast2SMS, or Generic HTTP
- add, edit, delete, and save registered numbers
- view masked phone numbers and last status
- clear or export the notification log

Alert cooldown is configurable in Settings: `30`, `60`, `120`, or `300` seconds.
