# Technical Architecture

## Pipeline

```text
Video Frame
  -> YOLOv8 animal-like object detector
  -> Crop each animal box
  -> Existing Keras .h5 classifier
  -> Final species label decision
  -> Dangerous animal evaluation
  -> UI overlay, snapshot, event log, report, optional SMS
```

## Core Modules

- `app/core/yolo_detector.py`: loads YOLOv8 and returns filtered animal-like boxes.
- `app/core/hybrid_detector.py`: combines YOLO boxes with the existing classifier.
- `app/core/alert_service.py`: applies dangerous animal, confidence, repeated detection, and cooldown rules.
- `app/core/notification_service.py`: sends SMS if enabled in local config; otherwise records disabled status.
- `app/core/snapshot_service.py`: saves alert evidence with bounding boxes.
- `app/core/report_service.py`: exports alert reports.

## Label Decision

For each YOLO animal-like box:

- If classifier confidence is at least `classifier_confidence`, use the classifier label.
- Otherwise, use the YOLO label.

This keeps the demo working even when the classifier is uncertain.
