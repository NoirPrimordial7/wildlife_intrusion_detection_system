from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.detection_localizer import draw_detection_overlay
from app.core.hybrid_detector import HybridDetector
from app.core.prediction_service import PredictionService
from app.utils.paths import ASSETS_DIR, REPORTS_DIR, relative_to_project
from app.utils.time_utils import file_timestamp


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:05.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate hybrid YOLO + classifier detection on sampled video frames. SMS is never sent.")
    parser.add_argument("video", nargs="?", help="Path to video file")
    parser.add_argument("--every", type=int, default=30, help="Sample every N frames")
    parser.add_argument("--max-frames", type=int, default=60, help="Maximum sampled frames to evaluate")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR), help="Directory for boxed frames and reports")
    parser.add_argument("--json-out", help="Exact JSON report path")
    parser.add_argument("--md-out", help="Exact Markdown report path")
    parser.add_argument("--frames-dir", help="Exact directory for boxed frames")
    args = parser.parse_args()

    if not args.video:
        parser.print_help()
        return 0

    video_path = Path(args.video)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return 1

    video_stem = video_path.stem
    output_dir = Path(args.output_dir) / f"hybrid_video_eval_{file_timestamp()}"
    frames_dir = Path(args.frames_dir) if args.frames_dir else output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    detector = HybridDetector(PredictionService())
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_index = 0
    sampled = 0
    results: list[dict[str, Any]] = []

    while sampled < args.max_frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if frame_index % max(1, args.every) == 0:
            result = detector.predict_frame(frame)
            timestamp = frame_index / max(fps, 1.0)
            danger = any(bool(item.get("is_dangerous")) for item in result.get("detections", []))
            boxed = draw_detection_overlay(frame, result, "DANGER" if danger else "LOW")
            boxed_path = frames_dir / f"frame_{frame_index:06d}.jpg"
            cv2.imwrite(str(boxed_path), boxed)
            results.append(
                {
                    "frame_number": frame_index,
                    "video_timestamp": format_timestamp(timestamp),
                    "display_label": result.get("display_label", result.get("label", "Unknown")),
                    "label": result.get("display_label", result.get("label", "Unknown")),
                    "final_label": result.get("final_label", result.get("label", "Unknown")),
                    "raw_classifier_label": result.get("raw_classifier_label", ""),
                    "normalized_classifier_label": result.get("normalized_classifier_label", ""),
                    "yolo_label": result.get("yolo_label", ""),
                    "confidence": result.get("confidence", 0.0),
                    "detector_mode": result.get("detector_mode", ""),
                    "processing_time_ms": result.get("processing_time_ms", 0.0),
                    "dangerous": danger,
                    "detections": result.get("detections", []),
                    "boxed_frame": relative_to_project(boxed_path),
                }
            )
            sampled += 1
        frame_index += 1

    cap.release()

    report = {
        "video": str(video_path),
        "sample_every_frames": args.every,
        "sampled_frames": sampled,
        "results": results,
    }
    json_path = Path(args.json_out) if args.json_out else ASSETS_DIR / "evaluation" / f"{video_stem}_hybrid_report.json"
    md_path = Path(args.md_out) if args.md_out else REPORTS_DIR / f"video_test_{video_stem}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")

    print(f"Sampled frames: {sampled}")
    print(f"JSON report: {relative_to_project(json_path)}")
    print(f"Markdown report: {relative_to_project(md_path)}")
    return 0


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Hybrid Video Evaluation Report",
        "",
        f"Video: `{report.get('video', '')}`",
        f"Sample every frames: {report.get('sample_every_frames')}",
        f"Sampled frames: {report.get('sampled_frames')}",
        "",
        "| Time | Frame | Display Label | Confidence | YOLO | Raw Classifier | Normalized Classifier | Dangerous | Processing |",
        "| --- | ---: | --- | ---: | --- | --- | --- | --- | ---: |",
    ]
    for row in report.get("results", []):
        primary = _primary_detection(row.get("detections", []))
        lines.append(
            f"| {row.get('video_timestamp')} | {row.get('frame_number')} | {row.get('display_label', row.get('label'))} | "
            f"{float(row.get('confidence', 0.0)):.1%} | {primary.get('yolo_label', row.get('yolo_label') or '--')} | "
            f"{primary.get('raw_classifier_label', row.get('raw_classifier_label') or '--')} | "
            f"{primary.get('normalized_classifier_label', row.get('normalized_classifier_label') or '--')} | {row.get('dangerous')} | "
            f"{float(row.get('processing_time_ms', 0.0)):.1f} ms |"
        )
    return "\n".join(lines)


def _primary_detection(detections: Any) -> dict[str, Any]:
    if not isinstance(detections, list) or not detections:
        return {}
    valid = [item for item in detections if isinstance(item, dict)]
    if not valid:
        return {}
    dangerous = [item for item in valid if item.get("is_dangerous")]
    return max(dangerous or valid, key=lambda item: float(item.get("final_confidence", 0.0) or 0.0))


if __name__ == "__main__":
    raise SystemExit(main())
