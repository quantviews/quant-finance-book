"""Секреты (токены API) из переменных окружения или файла .env.

Файл .env лежит в корне книги и не попадает в git (см. .gitignore).
Образец – .env.example.

    from qf import secrets
    token = secrets.get("RUSTATA_TOKEN")
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Читает файл KEY=VALUE; пустые строки и комментарии (#) пропускаются."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get(name: str, required: bool = True) -> str | None:
    """Значение секрета: сначала из окружения, затем из .env."""
    value = os.environ.get(name) or load_env().get(name)
    if not value and required:
        raise KeyError(
            f"Не задан {name}. Скопируйте .env.example в .env в корне книги "
            f"и впишите значение (или задайте переменную окружения {name})."
        )
    return value or None
