from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "assets" / "reports" / "model_asset_scan_report.md"
EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".expo",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
    "__pycache__",
}
MODEL_EXTENSIONS = {".pt", ".onnx", ".engine", ".torchscript"}
YAML_EXTENSIONS = {".yaml", ".yml"}
ZIP_EXTENSIONS = {".zip"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SCRIPT_NAMES = {"train.py", "detect.py", "predict.py"}
SCRIPT_KEYWORDS = ("yolo", "ultralytics", "roboflow", "detect", "train")
DIRECTORY_NAMES = {"labels", "images", "train", "val", "valid", "test"}
RUN_FOLDER_KEYWORDS = ("runs\\detect", "train_model", "yolo_dataset")
DATASET_CONTEXT_KEYWORDS = ("yolo", "yolov8", "roboflow", "dataset", "train_model")


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def normalize_name(value: str) -> str:
    return value.replace("\\", "/").strip().casefold()


def is_excluded(path: Path) -> bool:
    return any(part.casefold() in EXCLUDED_DIR_NAMES for part in path.parts)


def looks_like_yolo_text(file_path: Path) -> bool:
    try:
        sample = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:5]
    except OSError:
        return False
    if not sample:
        return False
    for line in sample:
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) < 5:
            return False
        try:
            int(float(parts[0]))
            for value in parts[1:5]:
                float(value)
        except ValueError:
            return False
    return True


def parse_basic_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None

    text = path.read_text(encoding="utf-8", errors="ignore")
    if yaml is not None:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}

    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] = []
    current_dict: dict[int, str] = {}

    def flush() -> None:
        nonlocal current_key, current_list, current_dict
        if current_key is None:
            return
        if current_list:
            data[current_key] = current_list[:]
        elif current_dict:
            data[current_key] = dict(sorted(current_dict.items()))
        current_key = None
        current_list = []
        current_dict = {}

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith((" ", "\t")):
            flush()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                data[key] = value.strip("'\"")
            else:
                current_key = key
            continue

        if current_key is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            current_list.append(stripped[2:].strip().strip("'\""))
            continue
        if ":" in stripped:
            index_text, value = stripped.split(":", 1)
            index_text = index_text.strip()
            value = value.strip().strip("'\"")
            if index_text.isdigit():
                current_dict[int(index_text)] = value
    flush()
    return data


def yaml_summary(path: Path) -> dict[str, Any]:
    data = parse_basic_yaml(path)
    names = data.get("names")
    if isinstance(names, dict):
        ordered_names = [str(value) for _, value in sorted(names.items(), key=lambda item: int(item[0]))]
    elif isinstance(names, list):
        ordered_names = [str(value) for value in names]
    else:
        ordered_names = []
    nc = data.get("nc")
    if nc is None and ordered_names:
        nc = len(ordered_names)
    return {
        "train": data.get("train"),
        "val": data.get("val"),
        "test": data.get("test"),
        "names": ordered_names,
        "nc": nc,
    }


def try_load_ultralytics_model(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"attempted": True, "loaded": False}
    try:
        from ultralytics import YOLO  # type: ignore

        model = YOLO(str(path))
        result["loaded"] = True
        result["task"] = getattr(model, "task", None)
        names = getattr(getattr(model, "model", None), "names", None)
        if isinstance(names, dict):
            result["names"] = dict(names)
        else:
            result["names"] = names
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


@dataclass
class AssetRecord:
    path: Path
    size: int
    modified: str
    why_useful: str
    confidence: str
    extra: dict[str, Any]


class Scanner:
    def __init__(self, roots: list[Path]) -> None:
        unique_roots: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root.resolve()).casefold()
            if key not in seen and root.exists():
                seen.add(key)
                unique_roots.append(root.resolve())
        self.roots = unique_roots
        self.models: list[AssetRecord] = []
        self.datasets: list[AssetRecord] = []
        self.label_dirs: list[AssetRecord] = []
        self.image_dirs: list[AssetRecord] = []
        self.run_dirs: list[AssetRecord] = []
        self.scripts: list[AssetRecord] = []
        self.archives: list[AssetRecord] = []

    def scan(self) -> None:
        label_dir_map: dict[str, dict[str, Any]] = {}
        image_dir_map: dict[str, dict[str, Any]] = {}
        run_dir_map: dict[str, dict[str, Any]] = {}

        for root in self.roots:
            for current_root, dirnames, filenames in self._walk(root):
                current_path = Path(current_root)
                lower_path = normalize_name(str(current_path))

                for dirname in dirnames:
                    dir_path = current_path / dirname
                    normalized = normalize_name(str(dir_path))

                    if dirname.casefold() == "labels" and self._looks_like_dataset_context(dir_path):
                        label_dir_map[normalized] = self._summarize_label_dir(dir_path)
                    if dirname.casefold() == "images" and self._looks_like_dataset_context(dir_path):
                        image_dir_map[normalized] = self._summarize_image_dir(dir_path)
                    if dirname.casefold() in {"train", "val", "valid", "test"} and any(
                        token in normalized for token in ("yolov8", "roboflow", "dataset", "yolo")
                    ):
                        image_dir_map.setdefault(normalized, self._summarize_image_dir(dir_path))
                    if any(token in normalized for token in RUN_FOLDER_KEYWORDS):
                        run_dir_map[normalized] = {
                            "path": dir_path,
                            "why": "Looks like a YOLO training output or dataset staging folder.",
                            "confidence": "MEDIUM",
                        }

                if any(token in lower_path for token in RUN_FOLDER_KEYWORDS):
                    run_dir_map.setdefault(
                        lower_path,
                        {
                            "path": current_path,
                            "why": "Looks like a YOLO training output or dataset staging folder.",
                            "confidence": "MEDIUM",
                        },
                    )

                for filename in filenames:
                    file_path = current_path / filename
                    suffix = file_path.suffix.casefold()
                    lower_name = file_path.name.casefold()

                    if suffix in MODEL_EXTENSIONS:
                        self.models.append(self._model_record(file_path))
                    elif suffix in YAML_EXTENSIONS and self._is_relevant_yaml(file_path):
                        self.datasets.append(self._yaml_record(file_path))
                    elif suffix in ZIP_EXTENSIONS:
                        self.archives.append(self._zip_record(file_path))
                    elif self._is_script_candidate(file_path):
                        self.scripts.append(self._script_record(file_path))
                    elif lower_name in {"classes.txt", "obj.names"}:
                        self.scripts.append(self._script_record(file_path, kind="classes"))
                    elif suffix == ".txt" and "labels" in lower_name and file_path.parent.name.casefold() != "labels":
                        self.scripts.append(self._script_record(file_path, kind="labels"))

        self.label_dirs = self._records_from_map(label_dir_map)
        self.image_dirs = self._records_from_map(image_dir_map)
        self.run_dirs = self._records_from_map(run_dir_map)

    def _walk(self, root: Path):
        for current_root, dirnames, filenames in __import__("os").walk(root):
            dirnames[:] = [name for name in dirnames if name.casefold() not in EXCLUDED_DIR_NAMES]
            yield current_root, dirnames, filenames

    def _stat_info(self, path: Path) -> tuple[int, str]:
        stat = path.stat()
        return int(stat.st_size), format_dt(stat.st_mtime)

    def _looks_like_dataset_context(self, path: Path) -> bool:
        normalized = normalize_name(str(path))
        if any(keyword in normalized for keyword in DATASET_CONTEXT_KEYWORDS):
            return True
        parent = path.parent
        if path.name.casefold() == "images" and (parent / "labels").exists():
            return True
        if path.name.casefold() == "labels" and (parent / "images").exists():
            return True
        if parent.name.casefold() in {"train", "val", "valid", "test"}:
            return True
        return False

    def _is_relevant_yaml(self, path: Path) -> bool:
        name = path.name.casefold()
        if name in {"data.yaml", "dataset.yaml", "args.yaml"}:
            return True
        normalized = normalize_name(str(path))
        return "yolo" in normalized or "roboflow" in normalized

    def _is_script_candidate(self, path: Path) -> bool:
        name = path.name.casefold()
        if name in SCRIPT_NAMES or path.suffix.casefold() == ".ipynb":
            return True
        return any(keyword in name for keyword in SCRIPT_KEYWORDS) and path.suffix.casefold() in {".py", ".ipynb"}

    def _model_record(self, path: Path) -> AssetRecord:
        size, modified = self._stat_info(path)
        usefulness = "Model weight file. Could be loaded for inference or metadata inspection."
        confidence = "HIGH" if path.name.casefold() in {"best.pt", "last.pt"} else "MEDIUM"
        validation = try_load_ultralytics_model(path)
        if "floor planner" in normalize_name(str(path)):
            usefulness = "YOLO checkpoint from an older custom object-detection project, but it appears unrelated to wildlife."
            confidence = "MEDIUM"
        return AssetRecord(path, size, modified, usefulness, confidence, {"validation": validation})

    def _yaml_record(self, path: Path) -> AssetRecord:
        size, modified = self._stat_info(path)
        summary = yaml_summary(path)
        confidence = "HIGH" if path.name.casefold() in {"data.yaml", "dataset.yaml"} else "MEDIUM"
        usefulness = "Dataset configuration file. Useful for reconstructing dataset layout and class names."
        if "floor planner" in normalize_name(str(path)):
            usefulness = "YOLO dataset YAML, but the classes appear to describe floor-plan objects rather than wildlife."
            confidence = "LOW"
        return AssetRecord(path, size, modified, usefulness, confidence, summary)

    def _summarize_label_dir(self, path: Path) -> dict[str, Any]:
        label_files = sorted([child for child in path.glob("*.txt") if child.is_file()])
        label_count = len(label_files)
        yolo_like = sum(1 for file_path in label_files[:25] if looks_like_yolo_text(file_path))
        parent = path.parent
        sibling_images = parent / "images"
        sibling_image_count = 0
        if sibling_images.exists():
            sibling_image_count = sum(
                1 for child in sibling_images.iterdir() if child.is_file() and child.suffix.casefold() in IMAGE_EXTENSIONS
            )
        structure = "YOLO format" if label_count > 0 and yolo_like > 0 else "unknown"
        return {
            "path": path,
            "why": "Label directory with text annotations near image folders.",
            "confidence": "HIGH" if structure == "YOLO format" else "MEDIUM",
            "label_count": label_count,
            "nearby_image_count": sibling_image_count,
            "structure": structure,
        }

    def _summarize_image_dir(self, path: Path) -> dict[str, Any]:
        image_count = 0
        try:
            image_count = sum(1 for child in path.iterdir() if child.is_file() and child.suffix.casefold() in IMAGE_EXTENSIONS)
        except OSError:
            image_count = 0
        return {
            "path": path,
            "why": "Image folder that may belong to a train/val/test dataset split.",
            "confidence": "HIGH" if image_count > 0 else "MEDIUM",
            "image_count": image_count,
        }

    def _script_record(self, path: Path, kind: str = "script") -> AssetRecord:
        size, modified = self._stat_info(path)
        if kind == "classes":
            usefulness = "Class-name file. Useful when matching checkpoint outputs to labels."
            confidence = "MEDIUM"
        elif kind == "labels":
            usefulness = "Text file that may describe labels or annotations."
            confidence = "LOW"
        else:
            usefulness = "Training or detection script/notebook that may document prior YOLO work."
            confidence = "MEDIUM"
        return AssetRecord(path, size, modified, usefulness, confidence, {})

    def _zip_record(self, path: Path) -> AssetRecord:
        size, modified = self._stat_info(path)
        entries: list[str] = []
        interesting: dict[str, bool] = {"best.pt": False, "data.yaml": False, "labels/": False, "images/": False}
        zip_error = None
        try:
            with ZipFile(path) as archive:
                for entry in archive.infolist()[:200]:
                    entries.append(entry.filename)
                    lower = entry.filename.casefold()
                    if lower.endswith("best.pt"):
                        interesting["best.pt"] = True
                    if lower.endswith("data.yaml"):
                        interesting["data.yaml"] = True
                    if "/labels/" in lower or lower.startswith("labels/"):
                        interesting["labels/"] = True
                    if "/images/" in lower or lower.startswith("images/"):
                        interesting["images/"] = True
        except Exception as exc:
            zip_error = str(exc)

        usefulness = "Archive that may contain a dataset or model artifact."
        confidence = "MEDIUM"
        lower_path = normalize_name(str(path))
        if "animal_classification_model_final.zip" in lower_path:
            usefulness = "Classifier model archive from the wildlife project. Useful for classification backup, not YOLO detection."
            confidence = "MEDIUM"
        elif "floor planner" in lower_path:
            usefulness = "Archive from an older YOLO dataset export, but the contents appear unrelated to wildlife."
            confidence = "LOW"

        return AssetRecord(
            path,
            size,
            modified,
            usefulness,
            confidence,
            {"interesting_entries": interesting, "sample_entries": entries[:20], "zip_error": zip_error},
        )

    def _records_from_map(self, items: dict[str, dict[str, Any]]) -> list[AssetRecord]:
        records: list[AssetRecord] = []
        for payload in sorted(items.values(), key=lambda item: str(item["path"]).casefold()):
            path = Path(payload["path"])
            try:
                stat = path.stat()
                size = int(stat.st_size)
                modified = format_dt(stat.st_mtime)
            except OSError:
                size = 0
                modified = "unknown"
            extra = dict(payload)
            extra.pop("path", None)
            extra.pop("why", None)
            extra.pop("confidence", None)
            records.append(AssetRecord(path, size, modified, payload["why"], payload["confidence"], extra))
        return records


def dedupe_records(records: list[AssetRecord]) -> list[AssetRecord]:
    unique: dict[str, AssetRecord] = {}
    for record in records:
        unique[str(record.path).casefold()] = record
    return sorted(unique.values(), key=lambda item: str(item.path).casefold())


def confidence_rank(value: str) -> int:
    return {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(value.upper(), 3)


def choose_best_model(models: list[AssetRecord]) -> AssetRecord | None:
    if not models:
        return None
    return sorted(
        models,
        key=lambda record: (
            confidence_rank(record.confidence),
            0 if record.path.name.casefold() == "best.pt" else 1,
            0 if "custom" in normalize_name(str(record.path)) else 1,
            -record.size,
        ),
    )[0]


def choose_best_dataset(datasets: list[AssetRecord], label_dirs: list[AssetRecord]) -> AssetRecord | None:
    if datasets:
        return sorted(
            datasets,
            key=lambda record: (
                confidence_rank(record.confidence),
                0 if record.path.name.casefold() in {"data.yaml", "dataset.yaml"} else 1,
                0 if bool(record.extra.get("names")) else 1,
                -record.size,
            ),
        )[0]
    if not label_dirs:
        return None
    return sorted(label_dirs, key=lambda record: (confidence_rank(record.confidence), -record.size))[0]


def recommendation_text(models: list[AssetRecord], datasets: list[AssetRecord], label_dirs: list[AssetRecord]) -> list[str]:
    lines: list[str] = []
    best_model = choose_best_model(models)
    best_dataset = choose_best_dataset(datasets, label_dirs)
    lines.append(f"Best reusable model candidate: `{best_model.path}`" if best_model else "Best reusable model candidate: none found")
    lines.append(
        f"Best reusable dataset candidate: `{best_dataset.path}`" if best_dataset else "Best reusable dataset candidate: none found"
    )

    wildlife_model = next((record for record in models if "wild" in normalize_name(str(record.path))), None)
    if wildlife_model:
        lines.append("We can directly test an old wildlife-related YOLO model after installing a working `ultralytics` environment.")
    elif best_model is not None:
        lines.append("An old YOLO model was found, but it belongs to a floor-plan detector and should not be reused directly for wildlife.")
    else:
        lines.append("No old YOLO model was found in the requested roots.")

    wildlife_dataset = next(
        (record for record in datasets + label_dirs if "wild" in normalize_name(str(record.path)) or "animal" in normalize_name(str(record.path))),
        None,
    )
    if wildlife_dataset:
        lines.append("A potentially relevant wildlife dataset structure exists and could be copied after manual review.")
    elif best_dataset is not None:
        lines.append("A YOLO-style dataset was found, but it is unrelated to wildlife and should not be copied into this project.")
    else:
        lines.append("No reusable YOLO wildlife dataset was found in the requested roots.")

    lines.append(
        "Copy recommendation: do not copy any old YOLO assets into `wildlife_alert_system_clean/models/yolo/` or "
        "`wildlife_alert_system_clean/data/yolo_datasets/` until a wildlife-specific model or dataset is identified."
    )

    if best_model is not None:
        lines.append(
            "Exact next command to test the best found model: "
            f"`.\\.venv\\Scripts\\python.exe -m pip install ultralytics torch torchvision && "
            f".\\.venv\\Scripts\\python.exe -c \"from ultralytics import YOLO; m=YOLO(r'{best_model.path}'); print(m.task, getattr(m.model, 'names', None))\"`"
        )
    else:
        lines.append(
            "Exact next command to test YOLO locally: "
            "`.\\.venv\\Scripts\\python.exe -m pip install ultralytics torch torchvision && "
            ".\\.venv\\Scripts\\python.exe -c \"from ultralytics import YOLO; m=YOLO('yolov8n.pt'); print(m.task, getattr(m.model, 'names', None))\"`"
        )
    return lines


def render_section(title: str, records: list[AssetRecord]) -> list[str]:
    lines = [f"## {title}", ""]
    if not records:
        lines.append("None found.")
        lines.append("")
        return lines
    for record in records:
        lines.append(f"### `{record.path}`")
        lines.append(f"- Size: {format_size(record.size)}")
        lines.append(f"- Modified: {record.modified}")
        lines.append(f"- Why it might be useful: {record.why_useful}")
        lines.append(f"- Confidence: {record.confidence}")
        for key, value in record.extra.items():
            if value in (None, "", [], {}):
                continue
            pretty_value = json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- {key}:")
            lines.append("")
            lines.append("```text")
            lines.append(pretty_value)
            lines.append("```")
        lines.append("")
    return lines


def build_report(scanner: Scanner) -> str:
    models = dedupe_records(scanner.models)
    datasets = dedupe_records(scanner.datasets)
    label_dirs = dedupe_records(scanner.label_dirs)
    image_dirs = dedupe_records(scanner.image_dirs)
    run_dirs = dedupe_records(scanner.run_dirs)
    scripts = dedupe_records(scanner.scripts)
    archives = dedupe_records(scanner.archives)

    lines = [
        "# Model Asset Scan Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Roots Scanned",
        "",
    ]
    for root in scanner.roots:
        lines.append(f"- `{root}`")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Model weight files found: {len(models)}",
            f"- Dataset YAML files found: {len(datasets)}",
            f"- YOLO label folders found: {len(label_dirs)}",
            f"- Image dataset folders found: {len(image_dirs)}",
            f"- Training run folders found: {len(run_dirs)}",
            f"- YOLO-related scripts/notebooks found: {len(scripts)}",
            f"- Zip archives found: {len(archives)}",
            "",
            "## Recommendation",
            "",
        ]
    )
    for line in recommendation_text(models, datasets, label_dirs):
        lines.append(f"- {line}")
    lines.append("")
    lines.extend(render_section("Model Weight Files", models))
    lines.extend(render_section("Dataset YAML Files", datasets))
    lines.extend(render_section("YOLO Label Folders", label_dirs))
    lines.extend(render_section("Image Dataset Folders", image_dirs))
    lines.extend(render_section("Training Run Folders", run_dirs))
    lines.extend(render_section("YOLO-Related Scripts and Notebooks", scripts))
    lines.extend(render_section("Zip Archives", archives))
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan project roots for reusable YOLO or dataset assets.")
    parser.add_argument("--roots", nargs="+", required=True, help="Root folders to scan recursively.")
    parser.add_argument("--report", default=str(REPORT_PATH), help="Markdown report output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(value) for value in args.roots]
    scanner = Scanner(roots)
    scanner.scan()
    report = build_report(scanner)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Report written to: {report_path}")
    print(f"Models found: {len(dedupe_records(scanner.models))}")
    print(f"Datasets found: {len(dedupe_records(scanner.datasets))}")
    best_model = choose_best_model(dedupe_records(scanner.models))
    best_dataset = choose_best_dataset(dedupe_records(scanner.datasets), dedupe_records(scanner.label_dirs))
    print(f"Best model candidate: {best_model.path if best_model else 'none'}")
    print(f"Best dataset candidate: {best_dataset.path if best_dataset else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
