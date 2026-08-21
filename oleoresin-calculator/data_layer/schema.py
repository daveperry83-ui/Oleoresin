"""Modelo de producto unificado para ambos catálogos."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional

from core.units import SpecRange

#: Un producto puede estar vigente, anulado (tachado en el ASKRC) o reemplazado
#: por otro código ("Converted To"). Solo ``active`` es ofertable.
STATUS_ACTIVE = "active"
STATUS_VOID = "void"
STATUS_CONVERTED = "converted"

SOURCE_FIRST_CHOICE = "first_choice"
SOURCE_EXTENDED = "extended"

SOURCE_LABELS = {
    SOURCE_FIRST_CHOICE: "First Choice",
    SOURCE_EXTENDED: "Extended",
}

STATUS_LABELS = {
    STATUS_ACTIVE: "Vigente",
    STATUS_VOID: "Void / Do Not Sample",
    STATUS_CONVERTED: "Reemplazado",
}

#: Etiquetas de familia que son mezclas o categorías de producto, no un
#: botánico único. No tienen un equivalente de especia natural con el que
#: calcular un factor de reemplazo 1:1, así que se excluyen del selector de
#: la calculadora y del formulario estructurado del recomendador — pero
#: siguen siendo buscables normalmente (por nombre o código) en el
#: recomendador de texto libre.
NON_BOTANICAL_FAMILIES = frozenset({
    "oleoresin blends",
    "oil blends",
    "other essential oil blends",
    "other natural extractive",
    "colours",
    "salsa",
    "co2 based product",
    "organic oleoresin",
    "pepper",
})


@dataclass
class Product:
    code: str
    description: str
    source: str
    family: str = ""
    sheet: str = ""
    solubility: str = "unknown"
    form: str = ""
    legal_status: str = ""
    kosher: Optional[bool] = None
    halal: Optional[bool] = None
    vegan: Optional[bool] = None
    gmo_free: Optional[bool] = None
    allergen_free: Optional[bool] = None
    contains_soy: Optional[bool] = None
    organic: bool = False
    shelf_life_months: Optional[float] = None
    dosage_level: str = ""
    status: str = STATUS_ACTIVE
    converted_to: str = ""
    notes: str = ""
    analytes: Dict[str, SpecRange] = field(default_factory=dict)

    @property
    def is_offerable(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def has_marker(self) -> bool:
        return bool(self.analytes)

    def analyte_display(self, name: str) -> str:
        r = self.analytes.get(name)
        return r.format() if r else "—"

    def to_row(self) -> dict:
        row = asdict(self)
        row["analytes"] = json.dumps(
            {
                k: {
                    "low": v.low,
                    "high": v.high,
                    "kind": v.kind,
                    "unit": v.unit,
                    "raw": v.raw,
                }
                for k, v in self.analytes.items()
            },
            ensure_ascii=False,
        )
        return row

    @staticmethod
    def from_row(row: dict) -> "Product":
        data = dict(row)
        blob = data.pop("analytes", "") or "{}"
        parsed = json.loads(blob) if isinstance(blob, str) else {}
        analytes = {
            k: SpecRange(v["low"], v["high"], v["kind"], v.get("unit"), v.get("raw", ""))
            for k, v in parsed.items()
        }
        for key in ("kosher", "halal", "vegan", "gmo_free", "allergen_free", "contains_soy"):
            if key in data and data[key] is not None:
                try:
                    import pandas as pd

                    if pd.isna(data[key]):
                        data[key] = None
                except Exception:
                    pass
        allowed = {f for f in Product.__dataclass_fields__}
        data = {k: v for k, v in data.items() if k in allowed}
        return Product(analytes=analytes, **data)


#: Analitos que la app sabe usar como marcador de reemplazo, en orden de
#: preferencia cuando un producto declara más de uno.
MARKER_PRIORITY = (
    "colour",
    "capsaicin",
    "piperine",
    "curcumin",
    "carnosic_acid",
    "vanillin",
    "volatile_oil",
)

MARKER_LABELS = {
    "volatile_oil": "Aceite volátil",
    "piperine": "Piperina",
    "curcumin": "Curcumina",
    "capsaicin": "Capsaicina",
    "colour": "Color",
    "scoville": "Scoville",
    "carnosic_acid": "Ácido carnósico",
    "vanillin": "Vainillina",
}

MARKER_LABELS_EN = {
    "volatile_oil": "Volatile oil",
    "piperine": "Piperine",
    "curcumin": "Curcumin",
    "capsaicin": "Capsaicin",
    "colour": "Colour",
    "scoville": "Scoville",
    "carnosic_acid": "Carnosic acid",
    "vanillin": "Vanillin",
}


def marker_label(key: str, language: str = "es") -> str:
    table = MARKER_LABELS_EN if language == "en" else MARKER_LABELS
    return table.get(key, key)

#: El factor de reemplazo teórico solo es válido 1:1 cuando el atributo que el
#: cliente compra ES el marcador. Para aceite volátil el perfil sensorial de la
#: oleorresina no es idéntico al de la especia molida.
DEFAULT_EFFICIENCY = {
    "colour": 1.00,
    "capsaicin": 1.00,
    "scoville": 1.00,
    "piperine": 0.95,
    "curcumin": 1.00,
    "carnosic_acid": 1.00,
    "vanillin": 0.95,
    "volatile_oil": 0.85,
}


def pick_marker(analytes: Dict[str, SpecRange]) -> Optional[str]:
    for name in MARKER_PRIORITY:
        if name in analytes:
            return name
    return next(iter(analytes), None)
