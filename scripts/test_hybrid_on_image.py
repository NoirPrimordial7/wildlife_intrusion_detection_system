from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.detection_localizer import draw_detection_overlay
from app.core.hybrid_detector import HybridDetector
from app.core.prediction_service import PredictionService
from app.utils.image_utils import load_image_as_bgr
from app.utils.paths import REPORTS_DIR, relative_to_project
from app.utils.time_utils import file_timestamp


def main() -> int:
    parser = argparse.ArgumentParser(description="Run YOLO + classifier hybrid detection on one image.")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR), help="Directory for boxed output image and JSON result")
    args = parser.parse_args()

    frame = load_image_as_bgr(args.image)
    detector = HybridDetector(PredictionService())
    result = detector.predict_frame(frame)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"hybrid_image_{file_timestamp()}"
    boxed_path = output_dir / f"{stem}.jpg"
    json_path = output_dir / f"{stem}.json"

    overlay = draw_detection_overlay(frame, result, "DANGER" if any(d.get("is_dangerous") for d in result.get("detections", [])) else "LOW")
    cv2.imwrite(str(boxed_path), overlay)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Label: {result.get('label')} ({float(result.get('confidence', 0.0)):.1%})")
    print(f"Detections: {len(result.get('detections', []))}")
    print(f"Boxed image: {relative_to_project(boxed_path)}")
    print(f"JSON result: {relative_to_project(json_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
