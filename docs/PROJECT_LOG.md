# Project Log

## Current Scope

The system is now a PC-based wildlife intrusion detection demo. It analyzes uploaded videos or webcam frames, detects animal-like objects with YOLO, classifies cropped animals with the existing `.h5` model, and triggers local evidence capture plus optional SMS alerts.

## Completed Demo Features

- Video Intrusion Detection mode with upload, first-frame preview, Start Detection, Pause, Resume, Stop, speed control, and detection interval.
- YOLOv8 animal-like object detection using `ultralytics`.
- Hybrid YOLO + classifier species decision.
- Bounding boxes, labels, confidence values, processing time, frame number, and video timestamp in the UI.
- Dangerous animal alert logic with repeated detection and cooldown.
- Snapshot evidence, alert event logs, notification logs, and report export.
- SMS provider-ready notification service with Twilio, Fast2SMS, and generic HTTP support, disabled by default.
- Evaluation scripts for images and videos.

## Demo Priority

For the final demo, use a clear wildlife video where a target animal is visible. The app is designed to show the pipeline and alert flow clearly; it is not a trained production detector for all forest conditions yet.

## Video Testing Status

Checked `assets/test_videos/` on 2026-04-27. Eight sample videos were evaluated with:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py "<video_path>" --every 15 --max-frames 120
```

The evaluator writes:

- `assets/reports/video_test_<video_name>.md`
- `assets/evaluation/<video_name>_hybrid_report.json`
- `assets/evaluation/<video_name>_frames/`

The consolidated summary is:

- `assets/reports/hybrid_video_test_summary.md`
- `assets/evaluation/hybrid_video_test_summary.json`

## Tuning Matrix

Tested these safe variants on the most useful representative clips:

- `yolo_confidence`: `0.20`, `0.25`, `0.35`
- `classifier_confidence`: `0.50`, `0.60`, `0.70`
- `crop_padding`: `0.10`, `0.15`, `0.25`

Chosen final demo configuration:

```json
{
  "yolo_confidence": 0.25,
  "classifier_confidence": 0.70,
  "crop_padding": 0.15
}
```

This keeps YOLO reasonably sensitive while reducing low-confidence classifier overrides.

## Best Demo Clips

- `Screen_Recording_20260424_194258_YouTube.mp4`: best for a tiger-style danger alert. Final evaluation found 46 sampled frames, 33 detections, 17 dangerous frames, and alert simulation would trigger on `Tiger`.
- `Screen_Recording_20260424_194012_YouTube.mp4`: best for elephant/hippo-style detections. Final evaluation found 29 sampled frames, 28 detections, 17 dangerous frames, and alert simulation would trigger on `elephant`.
