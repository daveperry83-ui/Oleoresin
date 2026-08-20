"""Localización.

La versión anterior mantenía dos diccionarios paralelos escritos a mano, así
que agregar una clave a un solo idioma provocaba ``KeyError`` en tiempo de
ejecución sin que nadie lo notara hasta la demo. Aquí hay un solo archivo con
ambos idiomas por clave, y ``check_parity`` lo verifica en los tests.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

LANGUAGES = {"es": "Español", "en": "English"}
DEFAULT_LANGUAGE = "es"
_PATH = Path(__file__).with_name("i18n.json")


@lru_cache(maxsize=1)
def _load() -> Dict[str, Dict[str, str]]:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def check_parity() -> List[str]:
    """Claves que no están traducidas en todos los idiomas."""
    missing = []
    for key, values in _load().items():
        for lang in LANGUAGES:
            if lang not in values or not values[lang]:
                missing.append(f"{key}[{lang}]")
    return missing


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = language if language in LANGUAGES else DEFAULT_LANGUAGE

    def __call__(self, key: str, **kwargs) -> str:
        entry = _load().get(key)
        if entry is None:
            return key
        text = entry.get(self.language) or entry.get(DEFAULT_LANGUAGE) or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text
