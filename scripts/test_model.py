from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from tensorflow.keras.models import load_model

from app.utils.paths import CLASS_NAMES_PATH, MODEL_PATH, load_json


def load_class_names() -> list[str]:
    payload = load_json(CLASS_NAMES_PATH, {})
    if isinstance(payload, dict) and isinstance(payload.get("class_names"), list):
        return [str(name) for name in payload["class_names"]]
    if isinstance(payload, list):
        return [str(name) for name in payload]
    raise ValueError(f"Unsupported class_names.json format: {CLASS_NAMES_PATH}")


def input_shape_for_dummy(input_shape) -> tuple[int, ...]:
    if isinstance(input_shape, list):
        input_shape = input_shape[0]
    if not isinstance(input_shape, tuple):
        return (1, 224, 224, 3)
    dims = [1 if dim is None else int(dim) for dim in input_shape]
    if len(dims) == 3:
        dims.insert(0, 1)
    return tuple(dims)


def main() -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    class_names = load_class_names()
    print(f"Model path: {MODEL_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Class count: {len(class_names)}")

    model = load_model(str(MODEL_PATH))
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")

    dummy_shape = input_shape_for_dummy(model.input_shape)
    dummy = np.zeros(dummy_shape, dtype="float32")
    output = model.predict(dummy, verbose=0)
    if isinstance(output, list):
        output = output[0]
    scores = np.asarray(output).reshape(-1)
    if scores.size == 0:
        raise RuntimeError("Model returned empty output")

    top_index = int(np.argmax(scores))
    top_label = class_names[top_index] if top_index < len(class_names) else f"class_{top_index}"
    print(f"Dummy prediction vector size: {scores.size}")
    print(f"Top dummy prediction: {top_label} ({float(scores[top_index]):.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

