"""Unificación de los dos catálogos y acceso al índice local.

Regla de negocio: ante duplicidad de código, **First Choice manda**. Si el
producto existe en ambas listas se conserva la ficha de First Choice y se
completan los campos vacíos con lo que aporte el ASKRC — que suele traer los
marcadores numéricos que a First Choice le faltan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from data_layer.schema import (
    NON_BOTANICAL_FAMILIES,
    SOURCE_EXTENDED,
    SOURCE_FIRST_CHOICE,
    STATUS_ACTIVE,
    Product,
)

DEFAULT_INDEX = Path("data/catalog.parquet")
DEFAULT_COMPETITOR_INDEX = Path("data/competitors.parquet")

_MERGEABLE = (
    "solubility", "form", "legal_status", "kosher", "halal", "vegan",
    "gmo_free", "allergen_free", "contains_soy", "shelf_life_months",
    "dosage_level", "notes", "family",
)


@dataclass
class Catalog:
    products: List[Product] = field(default_factory=list)
    competitors: List = field(default_factory=list)

    # ---------------------------------------------------------------- acceso
    def __len__(self) -> int:
        return len(self.products)

    @property
    def offerable(self) -> List[Product]:
        """Solo lo que se puede ofrecer: excluye tachados y reemplazados."""
        return [p for p in self.products if p.is_offerable]

    def by_code(self, code: str) -> Optional[Product]:
        key = (code or "").strip().upper()
        for p in self.products:
            if p.code.upper() == key:
                return p
        return None

    def families(self) -> List[str]:
        return sorted({p.family for p in self.offerable if p.family})

    def family_counts(self, *, matchable_only: bool = True) -> List[Tuple[str, int]]:
        """Familias ofertables con conteo de productos, de mayor a menor volumen.

        `matchable_only` excluye mezclas y categorías no botánicas (ver
        `NON_BOTANICAL_FAMILIES`) porque no tienen un equivalente de especia
        natural único: no se pueden usar en el selector del formulario
        estructurado ni en la calculadora de reemplazo.
        """
        counts: Dict[str, int] = {}
        for p in self.offerable:
            if not p.family or not p.has_marker:
                continue
            if matchable_only and p.family in NON_BOTANICAL_FAMILIES:
                continue
            counts[p.family] = counts.get(p.family, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def markers_for_family(self, family: str) -> List[str]:
        """Analitos que declaran realmente los productos de esa familia.

        Se calcula en vivo contra el catálogo cargado en vez de mantener un
        mapa hardcodeado, así que si mañana aparece un producto con un
        marcador nuevo el formulario estructurado lo detecta solo.
        """
        seen: Dict[str, int] = {}
        for p in self.offerable:
            if p.family != family:
                continue
            for name in p.analytes:
                seen[name] = seen.get(name, 0) + 1
        return [name for name, _ in sorted(seen.items(), key=lambda kv: -kv[1])]

    def marker_unit(self, family: str, marker: str) -> str:
        """Unidad más común para ese marcador dentro de la familia."""
        for p in self.offerable:
            if p.family == family and marker in p.analytes:
                unit = p.analytes[marker].unit
                if unit:
                    return unit
        return "%"

    def stats(self) -> Dict[str, int]:
        return {
            "total": len(self.products),
            "first_choice": sum(1 for p in self.products if p.source == SOURCE_FIRST_CHOICE),
            "extended": sum(1 for p in self.products if p.source == SOURCE_EXTENDED),
            "offerable": len(self.offerable),
            "void": sum(1 for p in self.products if p.status == "void"),
            "converted": sum(1 for p in self.products if p.status == "converted"),
            "with_marker": sum(1 for p in self.offerable if p.has_marker),
        }

    # ------------------------------------------------------------ persistencia
    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([p.to_row() for p in self.products])

    def save(self, path: str | Path = DEFAULT_INDEX) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_frame().to_parquet(path, index=False)
        if self.competitors:
            comp = pd.DataFrame([c.__dict__ for c in self.competitors])
            comp.to_parquet(path.with_name("competitors.parquet"), index=False)
        return path

    @staticmethod
    def load(path: str | Path = DEFAULT_INDEX) -> "Catalog":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"No existe el índice {path}. Genéralo con:\n"
                f"    python tools/build_index.py --first-choice <xlsx> --askrc <xlsx>"
            )
        frame = pd.read_parquet(path)
        products = [Product.from_row(row) for row in frame.to_dict("records")]

        competitors = []
        comp_path = path.with_name("competitors.parquet")
        if comp_path.exists():
            from data_layer.ingest_first_choice import CompetitorMatch

            competitors = [
                CompetitorMatch(**row) for row in pd.read_parquet(comp_path).to_dict("records")
            ]
        return Catalog(products=products, competitors=competitors)


def merge(first_choice: Iterable[Product], extended: Iterable[Product]) -> List[Product]:
    """Une ambas listas. First Choice gana; el ASKRC completa los huecos."""
    by_code: Dict[str, Product] = {}

    for product in first_choice:
        by_code[product.code.strip().upper()] = product

    for product in extended:
        key = product.code.strip().upper()
        existing = by_code.get(key)
        if existing is None:
            by_code[key] = product
            continue

        # First Choice manda en identidad y estatus, pero hereda del ASKRC los
        # analitos y atributos que le falten.
        for name, rng in product.analytes.items():
            existing.analytes.setdefault(name, rng)
        for attr in _MERGEABLE:
            current = getattr(existing, attr, None)
            if current in (None, "", "unknown"):
                incoming = getattr(product, attr, None)
                if incoming not in (None, "", "unknown"):
                    setattr(existing, attr, incoming)
        # Si el ASKRC lo marca como anulado o reemplazado, esa señal se respeta:
        # es la única de las dos fuentes que lleva el control de vigencia.
        if product.status != STATUS_ACTIVE:
            existing.status = product.status
            existing.converted_to = product.converted_to

    return list(by_code.values())


def build(first_choice_path: str | Path, askrc_path: str | Path) -> Catalog:
    from data_layer import ingest_askrc, ingest_first_choice

    fc = ingest_first_choice.load(first_choice_path)
    ext = ingest_askrc.load(askrc_path)
    competitors = ingest_first_choice.load_competitor_map(first_choice_path)
    return Catalog(products=merge(fc, ext), competitors=competitors)
