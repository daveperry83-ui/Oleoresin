"""Caché en disco para respuestas de red.

Solo guarda datos de mercado públicos (tipos de cambio, precios mayoristas).
El catálogo nunca pasa por aquí: no viaja ni se persiste fuera de ``data/``.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Optional

DEFAULT_PATH = Path("data/price_cache.json")


class DiskCache:
    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, blob: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            # Un disco de solo lectura degrada a "sin caché", no rompe la app.
            pass

    def get(self, key: str, ttl_hours: Optional[int] = 24) -> Optional[Any]:
        """``ttl_hours=None`` devuelve la entrada aunque esté vencida."""
        entry = self._read().get(key)
        if not entry:
            return None
        if ttl_hours is None:
            return entry.get("payload")
        try:
            stored = _dt.datetime.fromisoformat(entry["stored_at"])
        except (KeyError, ValueError):
            return None
        if _dt.datetime.now() - stored > _dt.timedelta(hours=ttl_hours):
            return None
        return entry.get("payload")

    def set(self, key: str, payload: Any) -> None:
        blob = self._read()
        blob[key] = {"stored_at": _dt.datetime.now().isoformat(), "payload": payload}
        self._write(blob)

    def stored_at(self, key: str) -> Optional[_dt.datetime]:
        entry = self._read().get(key)
        if not entry:
            return None
        try:
            return _dt.datetime.fromisoformat(entry["stored_at"])
        except (KeyError, ValueError):
            return None
