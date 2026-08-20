"""Referencias de mercado para especia seca.

No existe API pública de precios de oleorresinas — ese mercado se cotiza
bilateralmente. Lo que sí se puede automatizar es el precio de la **especia
seca**, que es justo el lado natural de la comparación y el input que más se
desactualiza.

Dos fuentes, en cascada:

1. ``data.gov.in`` — API REST oficial de precios mayoristas (mandi) de India.
   Requiere una clave gratuita propia; la de demostración pública está saturada
   y responde 429. Se configura en ``.streamlit/secrets.toml``.
2. ``indianspices.com`` (Spices Board India) — tabla HTML diaria. Aporta
   **grado**, que la API de mandi no da.

Ambas son precios domésticos de India: señal de tendencia, no costo de compra
en LATAM.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from core.units import inr_kg_to_usd_kg, inr_quintal_to_usd_kg
from pricing.cache import DiskCache
from pricing.provider import PriceProvider, ProviderChain, Quote

MANDI_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
MANDI_API = f"https://api.data.gov.in/resource/{MANDI_RESOURCE}"
SPICES_BOARD_URL = "https://www.indianspices.com/marketing/price/domestic/current-market-price.html"
TIMEOUT = 8

#: Familia botánica del catálogo -> nombre de commodity en cada fuente.
COMMODITY_MAP: Dict[str, Dict[str, str]] = {
    "pepper, black and green": {"mandi": "Black pepper", "board": "Pepper"},
    "pepper, white": {"mandi": "White Pepper", "board": "Pepper"},
    "turmeric": {"mandi": "Turmeric", "board": "Turmeric"},
    "ginger": {"mandi": "Ginger(Dry)", "board": "Ginger"},
    "cardamom": {"mandi": "Cardamoms", "board": "Small Cardamom"},
    "coriander": {"mandi": "Coriander(Leaves)", "board": "Coriander"},
    "cumin": {"mandi": "Cummin Seed(Jeera)", "board": "Cumin"},
    "garlic": {"mandi": "Garlic", "board": "Garlic"},
    "capsicum": {"mandi": "Dry Chillies", "board": "Chilli"},
    "chili": {"mandi": "Dry Chillies", "board": "Chilli"},
    "clove": {"mandi": "Cloves", "board": "Clove"},
    "nutmeg": {"mandi": "Nutmeg", "board": "Nutmeg"},
    "mace": {"mandi": "Nutmeg", "board": "Mace"},
    "fennel": {"mandi": "Fennel Seed(Saunf)", "board": "Fennel"},
    "fenugreek": {"mandi": "Methi Seeds", "board": "Fenugreek"},
    "celery": {"mandi": "Ajwan", "board": "Celery"},
}


def _usd_inr(fx_table=None) -> float:
    if fx_table is not None:
        try:
            return float(fx_table.rates["INR"])
        except (KeyError, TypeError, ValueError):
            pass
    from pricing.fx import FALLBACK_RATES

    return FALLBACK_RATES["INR"]


class USDAQuickStatsProvider(PriceProvider):
    """USDA QuickStats — Precios agrícolas de EEUU."""

    name = "USDA QuickStats"

    def __init__(self, api_key: Optional[str] = None, cache: Optional[DiskCache] = None, fx=None):
        self.api_key = api_key
        self.cache = cache or DiskCache()
        self.fx = fx

    def fetch(self, commodity: str) -> Optional[Quote]:
        if not self.api_key:
            return None

        # Mapeo de familias a nombres de items en USDA
        usda_items = {
            "pepper, black and green": "PEPPER, BLACK - PRICE RECEIVED",
            "turmeric": "TURMERIC - PRICE RECEIVED",
            "ginger": "GINGER - PRICE RECEIVED",
            "capsicum": "PEPPERS, CHILI - PRICE RECEIVED",
            "garlic": "GARLIC - PRICE RECEIVED",
        }

        data_item = usda_items.get(commodity)
        if not data_item:
            return None

        key = f"usda:{data_item}"
        payload = self.cache.get(key, ttl_hours=168)  # Una semana
        if payload is None:
            try:
                params = {
                    "key": self.api_key,
                    "format": "JSON",
                    "data_item": data_item,
                    "geographic_level_desc": "NATIONAL",
                    "year__GE": "2024",
                }
                url = f"https://quickstats.nass.usda.gov/api/api_GET/?{urllib.parse.urlencode(params)}"
                with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.cache.set(key, payload)
            except Exception:
                return None

        records = payload.get("data") or []
        if not records:
            return None

        # Tomar el precio más reciente
        prices: List[float] = []
        date: Optional[_dt.date] = None
        for record in records:
            try:
                price = float(record.get("Value", 0))
                if price > 0:
                    prices.append(price)
                    if date is None and record.get("Year"):
                        date = _dt.date(int(record.get("Year", 2024)), 1, 1)
            except (TypeError, ValueError):
                continue

        if not prices:
            return None

        # Precio medio en $/cwt (hundredweight) convertir a $/kg
        # 1 cwt = 45.36 kg
        median_cwt = sorted(prices)[len(prices) // 2]
        usd_kg = median_cwt / 45.36

        return Quote(
            value=usd_kg,
            currency="USD",
            unit="kg",
            source=self.name,
            date=date,
            url="https://quickstats.nass.usda.gov/",
            grade=f"mediana de {len(prices)} reportes",
            note="Precio agrícola USDA. Datos de EEUU, no LATAM.",
        )


class MandiProvider(PriceProvider):
    """API oficial de precios mayoristas de India (data.gov.in)."""

    name = "data.gov.in · Mandi Prices"

    def __init__(self, api_key: Optional[str] = None, cache: Optional[DiskCache] = None, fx=None):
        self.api_key = api_key
        self.cache = cache or DiskCache()
        self.fx = fx

    def fetch(self, commodity: str) -> Optional[Quote]:
        if not self.api_key:
            return None
        name = COMMODITY_MAP.get(commodity, {}).get("mandi")
        if not name:
            return None

        key = f"mandi:{name}"
        payload = self.cache.get(key, ttl_hours=24)
        if payload is None:
            params = {
                "api-key": self.api_key,
                "format": "json",
                "limit": "40",
                "filters[commodity]": name,
            }
            url = f"{MANDI_API}?{urllib.parse.urlencode(params)}"
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.cache.set(key, payload)

        records = payload.get("records") or []
        prices: List[float] = []
        date: Optional[_dt.date] = None
        for record in records:
            raw = record.get("modal_price") or record.get("max_price")
            try:
                prices.append(float(str(raw).replace(",", "")))
            except (TypeError, ValueError):
                continue
            if date is None:
                date = _parse_date(record.get("arrival_date"))
        if not prices:
            return None

        median = sorted(prices)[len(prices) // 2]
        usd_kg = inr_quintal_to_usd_kg(median, _usd_inr(self.fx))
        return Quote(
            value=usd_kg,
            currency="USD",
            unit="kg",
            source=self.name,
            date=date,
            url="https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi",
            grade=f"mediana de {len(prices)} mercados",
            note="Precio mayorista doméstico de India. Señal de tendencia, no costo de compra.",
        )


class SpicesBoardProvider(PriceProvider):
    """Tabla diaria del Spices Board de India. Aporta grado comercial."""

    name = "Spices Board India"

    def __init__(self, cache: Optional[DiskCache] = None, fx=None):
        self.cache = cache or DiskCache()
        self.fx = fx

    def fetch(self, commodity: str) -> Optional[Quote]:
        name = COMMODITY_MAP.get(commodity, {}).get("board")
        if not name:
            return None

        key = "spices_board:table"
        rows = self.cache.get(key, ttl_hours=24)
        if rows is None:
            rows = self._scrape()
            if rows:
                self.cache.set(key, rows)
        if not rows:
            return None

        target = name.lower()
        matches = [r for r in rows if target in str(r.get("spice", "")).lower()]
        if not matches:
            return None
        row = matches[0]
        try:
            inr_kg = float(str(row["price"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            return None

        return Quote(
            value=inr_kg_to_usd_kg(inr_kg, _usd_inr(self.fx)),
            currency="USD",
            unit="kg",
            source=self.name,
            date=_parse_date(row.get("date")),
            url=SPICES_BOARD_URL,
            grade=" · ".join(x for x in (row.get("grade"), row.get("market")) if x),
            note="Precio doméstico indicativo publicado por el Spices Board.",
        )

    def _scrape(self) -> List[dict]:
        try:
            import pandas as pd

            request = urllib.request.Request(
                SPICES_BOARD_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; RobertetVSC/2.0)"}
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                html = response.read().decode("utf-8", errors="replace")
            tables = pd.read_html(html)
        except Exception:
            return []

        rows: List[dict] = []
        for table in tables:
            cols = [str(c).strip().lower() for c in table.columns]
            if not any("spice" in c for c in cols):
                continue
            table.columns = cols
            for _, record in table.iterrows():
                price = _first_numeric(record, ("avg", "average", "max", "price"))
                if price is None:
                    continue
                rows.append(
                    {
                        "date": _text(record, ("date",)),
                        "spice": _text(record, ("spice",)),
                        "market": _text(record, ("market centre", "market")),
                        "grade": _text(record, ("grade",)),
                        "price": price,
                    }
                )
        return rows


def _text(record, keys) -> str:
    for key in keys:
        for column in record.index:
            if key in str(column).lower():
                value = record[column]
                if value is not None and str(value) != "nan":
                    return str(value).strip()
    return ""


def _first_numeric(record, keys) -> Optional[float]:
    for key in keys:
        for column in record.index:
            if key in str(column).lower():
                try:
                    return float(str(record[column]).replace(",", ""))
                except (TypeError, ValueError):
                    continue
    return None


def _parse_date(raw) -> Optional[_dt.date]:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d %b %Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def reference_price(commodity: str, *, api_key: Optional[str] = None, usda_key: Optional[str] = None, fx=None) -> Optional[Quote]:
    """Punto de entrada único. Devuelve ``None`` si ninguna fuente responde.

    Cascada de proveedores:
    1. USDA QuickStats (si hay clave)
    2. data.gov.in India Mandi (si hay clave)
    3. Spices Board India (siempre disponible)
    """
    cache = DiskCache()
    chain = ProviderChain(
        USDAQuickStatsProvider(api_key=usda_key, cache=cache, fx=fx),
        MandiProvider(api_key=api_key, cache=cache, fx=fx),
        SpicesBoardProvider(cache=cache, fx=fx),
    )
    return chain.fetch(commodity)


def supported_commodities() -> List[str]:
    return sorted(COMMODITY_MAP)
