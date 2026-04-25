from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.utils.paths import ALERT_EVENTS_PATH, REPORTS_DIR, load_json, relative_to_project
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

        animal_counts = Counter(str(event.get("animal", "Unknown")) for event in events)
        lines: list[str] = [
            "AI Wildlife Intrusion Detection and Alert System",
            "Alert Report",
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

        lines.extend(["", "Recent events:"])
        for event in events[-20:]:
            lines.append(
                f"- {event.get('timestamp', '')} | {event.get('animal', 'Unknown')} | "
                f"{float(event.get('confidence', 0.0)):.0%} | {event.get('camera_location', '')} | "
                f"{event.get('snapshot_path', '')}"
            )

        report_path = self.output_dir / f"wildlife_alert_report_{file_timestamp()}.txt"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return relative_to_project(report_path)

