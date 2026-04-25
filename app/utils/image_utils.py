from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageOps


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


def frame_to_pil(frame: np.ndarray) -> Image.Image:
    if frame is None:
        raise ValueError("Frame is empty")
    return Image.fromarray(bgr_to_rgb(frame))


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = image.convert("RGB")
    return rgb_to_bgr(np.array(rgb))


def load_image_as_bgr(path: str) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return pil_to_bgr(image)


def resize_to_fit(image: Image.Image, width: int, height: int) -> Image.Image:
    width = max(1, int(width))
    height = max(1, int(height))
    return ImageOps.contain(image, (width, height), method=Image.Resampling.LANCZOS)


def safe_filename_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"

