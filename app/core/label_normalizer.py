from __future__ import annotations


LABEL_MAP = {
    "elefante": "Elephant",
    "cane": "Dog",
    "cavallo": "Horse",
    "gallina": "Chicken",
    "gatto": "Cat",
    "mucca": "Cow",
    "pecora": "Sheep",
    "ragno": "Spider",
    "farfalla": "Butterfly",
    "scoiattolo": "Squirrel",
}


DISPLAY_LABEL_MAP = {
    "bird": "Bird",
    "cat": "Cat",
    "dog": "Dog",
    "horse": "Horse",
    "sheep": "Sheep",
    "cow": "Cow",
    "elephant": "Elephant",
    "bear": "Bear",
    "zebra": "Zebra",
    "giraffe": "Giraffe",
    "tiger": "Tiger",
    "leopard": "Leopard",
    "lion": "Lion",
    "wolf": "Wolf",
    "hyena": "Hyena",
    "crocodile": "Crocodile",
    "snake": "Snake",
    "boar": "Boar",
    "rhinoceros": "Rhinoceros",
    "hippopotamus": "Hippopotamus",
}


def normalize_key(label: str) -> str:
    return " ".join(str(label).replace("_", " ").split()).casefold()


def normalize_label(label: str) -> str:
    key = normalize_key(label)
    if key in LABEL_MAP:
        return LABEL_MAP[key]
    if key in DISPLAY_LABEL_MAP:
        return DISPLAY_LABEL_MAP[key]
    cleaned = " ".join(str(label).replace("_", " ").split()).strip()
    return cleaned or "Unknown"


def display_label(label: str) -> str:
    return normalize_label(label)


def is_normalized_from_raw(label: str) -> bool:
    return normalize_key(label) in LABEL_MAP
