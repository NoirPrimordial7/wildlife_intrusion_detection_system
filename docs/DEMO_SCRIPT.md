# Demo Script

## Opening

This is a PC-based AI Wildlife Intrusion Detection System. It is designed for forest-border and village safety demos where a camera or uploaded video is monitored for dangerous wild animals.

## Step 1: Start The App

Run:

```powershell
.\.venv\Scripts\python.exe app\main.py
```

## Step 2: Load A Video

Click Upload Video and select the demo wildlife clip. The first frame appears, but the video does not start automatically.

Use a clear clip where the animal is large enough for YOLO to draw a box. If the clip is still missing, place it in:

```text
assets/test_videos/
```

Recommended tested clips:

- Use `Screen_Recording_20260424_194258_YouTube.mp4` to demo a tiger-style danger alert.
- Use `Screen_Recording_20260424_194012_YouTube.mp4` to demo elephant/hippo-style detections.

## Step 3: Start Detection

Click Start Detection. The system runs YOLO on sampled frames, draws bounding boxes around animal-like objects, crops each box, and classifies the crop with the existing `.h5` model.

The system keeps monitoring continuously at the selected interval. The video should keep playing while the status box shows `AI Monitoring Active`, `Next check in`, and `Last checked`.

## Step 4: Explain The Display

Point out:

- Detected animal label and confidence.
- Thick bounding box on the animal with a label such as `Tiger 92% | YOLO: bear 71%`.
- Detection Mode: Hybrid YOLO + Classifier.
- AI processing time.
- Alert decision time.
- Video timestamp and frame number.
- Threat level.

The visible labels are normalized for the demo. For example, raw classifier labels like `ragno` or `elefante` are not shown directly in the UI; the detailed reports keep the raw classifier label, normalized classifier label, YOLO label, and displayed label.

Explain the two alert concepts clearly:

- `Current Detection` is what the AI sees right now.
- `Latest Confirmed Alert` is the last danger event that passed repeated detection and cooldown rules.

This means the current frame can show `Tiger WARNING` while the evidence card still shows an older confirmed `Elephant DANGER` snapshot.

## Step 5: Dangerous Animal Alert

When a dangerous animal is detected repeatedly and the cooldown allows it, the system shows a DANGER alert, saves a snapshot, logs an alert event, and prepares SMS notification status.

The danger section shows the animal name, confidence, video timestamp, snapshot preview, notification status, last SMS time, and cooldown remaining. SMS remains disabled unless explicitly enabled in Notification Settings.

## Step 6: Report

Click Export Report to generate a project report containing video information, thresholds, alert events, speed metrics, notification status, and snapshot paths.

## Closing

SMS is disabled by default for safety. Real providers such as Twilio or Fast2SMS can be enabled later through the local ignored `data/sms_config.json` file.

Enable SMS only during final demo if credits are available:

1. Open Notification Settings.
2. Toggle Enable Real SMS.
3. Confirm the trial-credit warning.
4. Select Twilio, Fast2SMS, or Generic HTTP.
5. Add a registered number in international format.
6. Use Test SMS only when real sending is intended.

## Pre-Demo Check

Before presenting, run:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_on_video.py "assets\test_videos\<video>.mp4" --every 15 --max-frames 120 --frames-dir "assets\evaluation\<video>_frames"
```

Open the generated Markdown report in `assets/reports/` and confirm the boxes and labels look acceptable for the selected clip.

For the current tested set, also open:

```text
assets/reports/hybrid_video_test_summary.md
```
