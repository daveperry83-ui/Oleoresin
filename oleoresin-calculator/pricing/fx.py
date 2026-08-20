"""Tipo de cambio real.

Corrige el bug más caro de la versión anterior: el selector de moneda solo
cambiaba el símbolo. Con 80 USD/kg y el selector en MXN la app mostraba
"$ 80" cuando el número correcto era ~1,359 — un error de un orden de magnitud
presentado con cara de dato.

Fuente: Frankfurter (referencia del Banco Central Europeo). API pública, sin
clave y sin límite de uso.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

from pricing.cache import DiskCache

API = "https://api.frankfurter.dev/v1/latest"
TIMEOUT = 6

#: Monedas ofrecidas en la UI. ARS no está en la referencia del BCE.
CURRENCIES = {
    "USD": ("$", "Dólar estadounidense"),
    "EUR": ("€", "Euro"),
    "MXN": ("$", "Peso mexicano"),
    "BRL": ("R$", "Real brasileño"),
    "CAD": ("$", "Dólar canadiense"),
    "COP": ("$", "Peso colombiano"),
    "INR": ("₹", "Rupia india"),
}

#: Último respaldo si no hay red ni caché. Se marca como obsoleto en la UI para
#: que nadie cotice con esto creyendo que es el spot del día.
FALLBACK_RATES: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.856,
    "MXN": 16.99,
    "BRL": 5.19,
    "CAD": 1.377,
    "COP": 4050.0,
    "INR": 87.5,
}


@dataclass(frozen=True)
class FxTable:
    base: str
    rates: Dict[str, float]
    date: Optional[_dt.date]
    source: str
    stale: bool = False

    def convert(self, amount: float, to: str) -> float:
        if to == self.base:
            return amount
        rate = self.rates.get(to)
        if rate is None:
            raise KeyError(f"Sin tipo de cambio para {to}")
        return amount * rate

    def provenance(self) -> str:
        if self.stale:
            return f"{self.source} · valores de respaldo, sin conexión"
        when = self.date.strftime("%d-%b-%Y") if self.date else "sin fecha"
        return f"{self.source} · {when}"


def symbol(currency: str) -> str:
    return CURRENCIES.get(currency, ("", ""))[0] or currency


def fetch(base: str = "USD", cache: Optional[DiskCache] = None, ttl_hours: int = 12) -> FxTable:
    """Devuelve la tabla de conversión. Nunca lanza."""
    cache = cache or DiskCache()
    key = f"fx:{base}"

    cached = cache.get(key, ttl_hours=ttl_hours)
    if cached is not None:
        return _from_payload(cached, base, stale=False)

    symbols = ",".join(c for c in CURRENCIES if c != base)
    url = f"{API}?base={base}&symbols={symbols}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        payload.setdefault("rates", {})[base] = 1.0
        cache.set(key, payload)
        return _from_payload(payload, base, stale=False)
    except Exception:
        pass

    # Sin red: caché vencida antes que respaldo estático.
    expired = cache.get(key, ttl_hours=None)
    if expired is not None:
        return _from_payload(expired, base, stale=True)

    rates = dict(FALLBACK_RATES)
    if base != "USD":
        divisor = FALLBACK_RATES.get(base)
        if divisor:
            rates = {k: v / divisor for k, v in FALLBACK_RATES.items()}
    return FxTable(base=base, rates=rates, date=None, source="Respaldo local", stale=True)


def _from_payload(payload: dict, base: str, *, stale: bool) -> FxTable:
    rates = dict(payload.get("rates", {}))
    rates.setdefault(base, 1.0)
    raw_date = payload.get("date")
    try:
        date = _dt.date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        date = None
    return FxTable(
        base=base,
        rates=rates,
        date=date,
        source="Frankfurter · referencia BCE",
        stale=stale,
    )
