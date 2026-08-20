"""Normalización de unidades y parseo de valores de especificación.

Este módulo es el que más cuidado necesita: los dos catálogos expresan el mismo
analito en escalas distintas (ASKRC guarda piperina como fracción 0.4, Product
Reference como porcentaje "37 - 40") y mezclan números con texto
("40,000 - 41,000 CU", "6.27 - 6.93% HPLC ~ 1M", "22 min").

Un error aquí se propaga silenciosamente a un precio. Ver tests/test_units.py.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

# Factor usado por Robertet en el ASKRC para derivar Scoville desde capsaicina
# medida por HPLC/UV expresada como fracción (0.0693 -> 815,294 SHU).
SHU_PER_CAPSAICIN_FRACTION = 11_764_705.88

_NUM = r"\d+(?:[.,]\d+)?"

#: Analitos reconocidos y su unidad canónica.
CANONICAL_UNITS = {
    "volatile_oil": "%",
    "piperine": "%",
    "curcumin": "%",
    "capsaicin": "%",
    "colour": "CU",
    "scoville": "SHU",
    "carnosic_acid": "%",
    "vanillin": "%",
}


class UnitError(ValueError):
    """La conversión pedida no tiene sentido físico."""


@dataclass(frozen=True)
class SpecRange:
    """Un valor de especificación: un intervalo, posiblemente semiabierto.

    ``kind`` conserva cómo se declaró originalmente para poder mostrarlo tal cual
    al usuario ("22 min" no es lo mismo que "22" aunque el mínimo coincida).
    """

    low: Optional[float]
    high: Optional[float]
    kind: str  # range | min | max | point
    unit: Optional[str] = None
    raw: str = ""

    def __post_init__(self) -> None:
        if self.low is None and self.high is None:
            raise UnitError(f"SpecRange sin ningún extremo: {self.raw!r}")
        if self.low is not None and self.high is not None and self.low > self.high:
            object.__setattr__(self, "low", self.high)
            object.__setattr__(self, "high", self.low)

    @property
    def midpoint(self) -> float:
        """Valor representativo para el cálculo de reemplazo.

        Para un rango es el punto medio; para un mínimo declarado ("22 min") es
        el propio mínimo, que es lo único que Robertet garantiza por contrato.
        """
        if self.low is not None and self.high is not None:
            return (self.low + self.high) / 2.0
        return self.low if self.low is not None else self.high  # type: ignore[return-value]

    @property
    def guaranteed(self) -> Optional[float]:
        """Lo que realmente se garantiza: el extremo inferior, si existe."""
        return self.low

    def contains(self, value: float) -> bool:
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        return True

    def satisfies(self, requested: "SpecRange") -> float:
        """Qué tanto este producto cumple lo que pide el cliente: 0..1.

        ``self`` es lo que ofrece Robertet, ``requested`` lo que pide el cliente.
        1.0 = todo el rango ofrecido cae dentro de lo pedido, así que cualquier
        lote cumple. Valores intermedios = solapa parcialmente, hay que
        confirmar lote. 0.0 = no cumple.

        Los intervalos semiabiertos ("≥ 18 %" contra "≥ 35 %") se evalúan por
        el extremo garantizado, no por la anchura: un mínimo de 18 no satisface
        un mínimo de 35 aunque ambos intervalos se solapen hacia el infinito.
        """
        o_lo = self.low if self.low is not None else -math.inf
        o_hi = self.high if self.high is not None else math.inf
        r_lo = requested.low if requested.low is not None else -math.inf
        r_hi = requested.high if requested.high is not None else math.inf

        if o_lo > r_hi or o_hi < r_lo:
            return 0.0
        if o_lo >= r_lo and o_hi <= r_hi:
            return 1.0

        # Solapamiento parcial: se mide sobre la parte finita del intervalo
        # ofrecido, que es lo que Robertet realmente puede entregar.
        inter_lo, inter_hi = max(o_lo, r_lo), min(o_hi, r_hi)
        offered_width = o_hi - o_lo
        if math.isfinite(offered_width) and offered_width > 0:
            return max(0.0, min((inter_hi - inter_lo) / offered_width, 1.0))

        # Intervalo ofrecido abierto o puntual: cumple a medias si el extremo
        # garantizado queda dentro, nada si no.
        anchor = self.guaranteed if self.guaranteed is not None else self.high
        if anchor is None:
            return 0.0
        return 0.5 if r_lo <= anchor <= r_hi else 0.0

    def overlap(self, other: "SpecRange") -> float:
        """Alias histórico de :meth:`satisfies`."""
        return self.satisfies(other)

    def format(self) -> str:
        u = f" {self.unit}" if self.unit else ""
        if self.kind == "min":
            return f"≥ {_fmt(self.low)}{u}"
        if self.kind == "max":
            return f"≤ {_fmt(self.high)}{u}"
        if self.kind == "point" or self.low == self.high:
            return f"{_fmt(self.midpoint)}{u}"
        return f"{_fmt(self.low)} – {_fmt(self.high)}{u}"


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:g}"


def _to_float(token: str) -> float:
    """Convierte '40,000' -> 40000.0 y '6,93' -> 6.93.

    La coma es separador de miles cuando quedan exactamente tres dígitos
    después; en cualquier otro caso se trata como separador decimal.
    """
    token = token.strip()
    if "," in token:
        head, _, tail = token.rpartition(",")
        if len(tail) == 3 and tail.isdigit() and "." not in token:
            token = token.replace(",", "")
        else:
            token = token.replace(",", ".")
    return float(token)


def detect_unit(text: str) -> Optional[str]:
    t = text.upper()
    if "SHU" in t or "SCOVILLE" in t:
        return "SHU"
    if "CU" in re.findall(r"\b[A-Z]+\b", t):
        return "CU"
    if "PPM" in t:
        return "ppm"
    if "%" in t:
        return "%"
    return None


def parse_spec_value(
    text, *, analyte: Optional[str] = None, assume_fraction: bool = False
) -> Optional[SpecRange]:
    """Interpreta una celda de especificación.

    Acepta los formatos reales encontrados en ambos catálogos::

        "22 min"                   -> min 22
        "19 - 21"                  -> range 19..21
        "40,000 - 41,000 CU"       -> range 40000..41000 CU
        "200 CU Max"               -> max 200 CU
        "6.27 - 6.93% HPLC ~ 1M"   -> range 6.27..6.93 %
        "8.5% curcumin"            -> point 8.5 %
        0.4  (float del ASKRC)     -> point 40 % si assume_fraction

    ``assume_fraction`` marca las columnas del ASKRC que guardan fracciones
    (0.4 == 40 %). Se aplica solo a analitos porcentuales, nunca a CU ni SHU.
    """
    if text is None:
        return None

    if isinstance(text, (int, float)) and not isinstance(text, bool):
        value = float(text)
        if math.isnan(value):
            return None
        unit = CANONICAL_UNITS.get(analyte or "", None)
        if assume_fraction and unit == "%" and 0 < value <= 1.0:
            value *= 100.0
        return SpecRange(value, value, "point", unit, str(text))

    raw = re.sub(r"\s+", " ", str(text)).strip()
    if not raw or raw.lower() in {"n/a", "na", "-", "—", "<not entered>", "none"}:
        return None

    unit = detect_unit(raw) or CANONICAL_UNITS.get(analyte or "", None)
    # "~ 1M" / "(2 MILLION CAP)" son anotaciones, no el valor medido.
    body = re.sub(r"~\s*\d+(\.\d+)?\s*(M|MILLION|K)\b", " ", raw, flags=re.I)
    body = re.sub(r"\(\s*\d[\d.,]*\s*(M|MILLION|K)[^)]*\)", " ", body, flags=re.I)

    def _scale(v: float) -> float:
        if assume_fraction and unit == "%" and 0 < v <= 1.0:
            return v * 100.0
        return v

    m = re.search(rf"({_NUM})\s*(?:%|CU|SHU)?\s*(?:-|–|—|a|to)\s*({_NUM})", body, re.I)
    if m:
        lo, hi = _scale(_to_float(m.group(1))), _scale(_to_float(m.group(2)))
        return SpecRange(lo, hi, "range", unit, raw)

    # El número puede estar separado de min/max por la unidad: "200 CU Max".
    m = re.search(rf"({_NUM})\s*(?:%|CU|SHU|ppm)?\s*(?:min|mín|minimum|minimo|mínimo)\b", body, re.I)
    if m:
        return SpecRange(_scale(_to_float(m.group(1))), None, "min", unit, raw)

    m = re.search(rf"({_NUM})\s*(?:%|CU|SHU|ppm)?\s*(?:max|máx|maximum|maximo|máximo)\b", body, re.I)
    if m:
        return SpecRange(None, _scale(_to_float(m.group(1))), "max", unit, raw)

    m = re.search(rf"(?:min|mín|minimum)\s*\.?\s*({_NUM})", body, re.I)
    if m:
        return SpecRange(_scale(_to_float(m.group(1))), None, "min", unit, raw)

    m = re.search(rf"(?:max|máx|maximum)\s*\.?\s*({_NUM})", body, re.I)
    if m:
        return SpecRange(None, _scale(_to_float(m.group(1))), "max", unit, raw)

    m = re.search(rf"(?:≥|>=|>)\s*({_NUM})", body)
    if m:
        return SpecRange(_scale(_to_float(m.group(1))), None, "min", unit, raw)

    m = re.search(rf"(?:≤|<=|<)\s*({_NUM})", body)
    if m:
        return SpecRange(None, _scale(_to_float(m.group(1))), "max", unit, raw)

    m = re.search(rf"({_NUM})", body)
    if m:
        v = _scale(_to_float(m.group(1)))
        return SpecRange(v, v, "point", unit, raw)

    return None


def capsaicin_to_shu(fraction_percent: float) -> float:
    """Convierte capsaicina (en %) a Scoville con el factor del ASKRC."""
    if fraction_percent < 0:
        raise UnitError("La capsaicina no puede ser negativa")
    return fraction_percent / 100.0 * SHU_PER_CAPSAICIN_FRACTION


def inr_quintal_to_usd_kg(inr_per_quintal: float, usd_to_inr: float) -> float:
    """Precio mandi (INR por quintal de 100 kg) -> USD por kg.

    Dos conversiones encadenadas; es exactamente donde se cuelan los errores.
    """
    if usd_to_inr <= 0:
        raise UnitError("Tipo de cambio USD/INR inválido")
    if inr_per_quintal < 0:
        raise UnitError("Precio negativo")
    return (inr_per_quintal / 100.0) / usd_to_inr


def inr_kg_to_usd_kg(inr_per_kg: float, usd_to_inr: float) -> float:
    if usd_to_inr <= 0:
        raise UnitError("Tipo de cambio USD/INR inválido")
    return inr_per_kg / usd_to_inr


#: Vocabulario controlado de solubilidad. Los catálogos usan cinco etiquetas
#: distintas para tres conceptos; el matcher filtra por este campo.
SOLUBILITY_MAP = {
    "OIL SOLUBLE": "oil",
    "OIL": "oil",
    "OIL-SOLUBLE": "oil",
    "WATER SOLUBLE": "water_soluble",
    "WATER": "water_soluble",
    "WATER DISPERSIBLE": "water_dispersible",
    "WATER DISPERSABLE": "water_dispersible",
    "WATER-DISPERSIBLE": "water_dispersible",
    "WD": "water_dispersible",
    "WS": "water_soluble",
    "OS": "oil",
    "EMULSION": "emulsion",
    "POWDER": "powder",
    "DRY": "powder",
}

SOLUBILITY_LABELS = {
    "oil": "Oil soluble",
    "water_soluble": "Water soluble",
    "water_dispersible": "Water dispersible",
    "emulsion": "Emulsion",
    "powder": "Powder",
    "unknown": "—",
}


def normalize_solubility(value) -> str:
    if value is None:
        return "unknown"
    key = re.sub(r"\s+", " ", str(value)).strip().upper()
    if not key:
        return "unknown"
    if key in SOLUBILITY_MAP:
        return SOLUBILITY_MAP[key]
    if "DISPERS" in key:
        return "water_dispersible"
    if "WATER" in key or key.startswith("WS"):
        return "water_soluble"
    if "OIL" in key:
        return "oil"
    if "EMULS" in key:
        return "emulsion"
    if "POWDER" in key or "DRY" in key:
        return "powder"
    return "unknown"


def normalize_yesno(value) -> Optional[bool]:
    """'Y'/'YES'/'K'/'H' -> True ; 'N'/'NO' -> False ; vacío -> None."""
    if value is None:
        return None
    key = str(value).strip().upper()
    if not key or key in {"<NOT ENTERED>", "-", "—", "N/A", "NA"}:
        return None
    if key in {"Y", "YES", "SI", "SÍ", "TRUE", "1", "K", "H", "KP"}:
        return True
    if key in {"N", "NO", "FALSE", "0"}:
        return False
    return None
