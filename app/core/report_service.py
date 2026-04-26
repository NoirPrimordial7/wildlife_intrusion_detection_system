from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.utils.paths import ALERT_CONFIG_PATH, ALERT_EVENTS_PATH, REGISTERED_USERS_PATH, REPORTS_DIR, load_json, relative_to_project
from app.utils.time_utils import file_timestamp


class ReportService:
    def __init__(self, events_path: Path = ALERT_EVENTS_PATH, output_dir: Path = REPORTS_DIR) -> None:
        self.events_path = events_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_alert_report(self) -> str:
        events = load_json(self.events_path, [])
        if not isinstance(events, list):
            events = []
        config = load_json(ALERT_CONFIG_PATH, {})
        if not isinstance(config, dict):
            config = {}
        registered_users = load_json(REGISTERED_USERS_PATH, [])
        if not isinstance(registered_users, list):
            registered_users = []

        animal_counts = Counter(str(event.get("animal", "Unknown")) for event in events)
        latest_event = events[-1] if events else {}
        dangerous_animals = config.get("dangerous_animals", [])
        if not isinstance(dangerous_animals, list):
            dangerous_animals = []

        lines: list[str] = [
            "AI Wildlife Intrusion Detection and Alert System",
            "PC Video Intrusion Detection Report",
            "",
            f"Video filename: {latest_event.get('video_filename', '--')}",
            f"Detection interval: {latest_event.get('ai_interval', config.get('detection_interval', '--'))}",
            f"Confidence threshold: {float(config.get('confidence_threshold', 0.0)):.0%}",
            f"Registered users count: {len(registered_users)}",
            f"Dangerous animal list: {', '.join(str(name) for name in dangerous_animals)}",
            "",
            f"Total alerts: {len(events)}",
            "",
            "Alerts by animal:",
        ]
        if animal_counts:
            for animal, count in animal_counts.most_common():
                lines.append(f"- {animal}: {count}")
        else:
            lines.append("- No alert events recorded yet")

        lines.extend(["", "All alert events:"])
        for event in events:
            lines.extend(
                [
                    f"- Timestamp: {event.get('timestamp', '')}",
                    f"  Video time: {event.get('detection_video_timestamp', '--')}",
                    f"  Frame number: {event.get('detection_frame_number', '--')}",
                    f"  Animal: {event.get('animal', 'Unknown')}",
                    f"  Confidence: {float(event.get('confidence', 0.0)):.0%}",
                    f"  Severity: {event.get('severity', event.get('threat_level', ''))}",
                    f"  AI processing time: {float(event.get('processing_time_ms', 0.0)):.2f} ms",
                    f"  Alert decision time: {float(event.get('alert_decision_time_ms', 0.0)):.2f} ms",
                    f"  Playback FPS: {float(event.get('playback_fps', 0.0)):.2f}",
                    f"  Notification status: {event.get('notification_status', '--')}",
                    f"  Snapshot path: {event.get('snapshot_path', '')}",
                    f"  Location note: {event.get('location_note', '')}",
                    "",
                ]
            )

        report_path = self.output_dir / f"wildlife_video_intrusion_report_{file_timestamp()}.txt"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return relative_to_project(report_path)
