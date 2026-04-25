# AI Wildlife Intrusion Detection and Alert System

## Problem statement

Villages near forest-border areas can face danger from wild animals entering farms, roads, and residential zones. A monitoring system needs to watch camera or CCTV-like footage, detect potentially dangerous animals, and create clear alerts without spamming repeated notifications.

## Solution

This project is a clean safety monitoring dashboard built with CustomTkinter. It loads the existing trained image classification model, runs predictions on webcam frames, demo videos, or uploaded images, evaluates danger rules, saves alert snapshots, records alert events, and keeps a notification service ready for future Firebase mobile alerts.

## Features

- Webcam monitoring with AI prediction every 1 second by default.
- Video demo mode with manual Start, Pause, Resume, Stop, Restart, -5 sec, +5 sec, speed, AI interval, and timeline controls.
- Image test mode for quick model checks.
- Threat levels: SAFE, WARNING, and DANGER.
- Alert throttling with confidence threshold, repeated detection requirement, and cooldown.
- Snapshot saving in `assets/alerts/`.
- Alert event logging in `data/alert_events.json`.
- Report export to `assets/reports/`.
- Firebase placeholder config for future mobile notification integration.

## Folder structure

```text
wildlife_alert_system_clean/
  app/
    main.py
    ui/
    core/
    utils/
  models/
    animal_classification_model_final.h5
  data/
    class_names.json
    animal_info.json
    alert_config.json
    alert_events.json
    firebase_config.example.json
  assets/
    alerts/
    reports/
    test_videos/
    test_images/
    reference_images/
  scripts/
  requirements.txt
```

## Setup on Windows

Double-click:

```text
setup_windows.bat
```

Or run:

```powershell
.\setup_windows.ps1
```

The script checks Git and Python 3.10, creates `.venv`, installs requirements, runs the environment check, and runs the model smoke test.

## Setup on Mac/Linux

```bash
chmod +x setup_unix.sh
./setup_unix.sh
```

The script checks Git and `python3.10`, creates `.venv`, installs requirements, runs the environment check, and runs the model smoke test.

## Run app

From the project folder:

```bash
python app/main.py
```

If using the created virtual environment on Windows:

```powershell
.\.venv\Scripts\python.exe app/main.py
```

If using the created virtual environment on Mac/Linux:

```bash
./.venv/bin/python app/main.py
```

## Demo flow

1. Start with `Upload Image` to confirm the model loads and produces predictions.
2. Use `Upload Video Demo` to select a CCTV-like video. The first frame appears, but playback does not auto-start.
3. Press `Start` in the video controls, choose playback speed, and choose AI interval.
4. Use `Start Webcam Monitoring` for live camera monitoring.
5. When alert rules are satisfied, the app saves a snapshot and appends an event.
6. Use `Export Report` to generate a text report from saved alert events.

## Alert logic

Alerts are triggered only when all conditions are true:

- The predicted animal is in `data/alert_config.json` under `dangerous_animals`.
- Confidence is greater than or equal to `confidence_threshold`.
- The same dangerous animal is detected repeatedly based on `required_repeated_detections`.
- The alert cooldown has passed.

Default example:

```text
Tiger detected 3 times with confidence >= 70%, and no alert in the last 120 seconds -> trigger DANGER alert.
```

## Firebase mobile notification future integration

The current notification service sends local console/UI alerts and safely skips Firebase if it is disabled or missing. Future Firebase setup can copy `data/firebase_config.example.json` to `data/firebase_config.json` and enable:

```json
{
  "enabled": true,
  "project_id": "your-firebase-project-id",
  "service_account_json": "path/to/service-account.json",
  "topic": "wildlife_alerts"
}
```

The method `send_fcm_notification(title, body, data=None)` is already present in `app/core/notification_service.py`.

## Limitations

The current model is image classification, not bounding-box detection. It predicts one main class for a frame or image and does not localize animals in the image.

Future upgrade: use YOLO or another object detection model for multiple animals, bounding boxes, tracking, and stronger CCTV monitoring behavior.
