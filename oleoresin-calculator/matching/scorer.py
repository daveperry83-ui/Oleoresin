"""Motor de recomendación: spec del cliente -> mejores productos Robertet.

Reglas duras, no negociables:

* Un producto **anulado** (tachado en el ASKRC) o **reemplazado** nunca entra al
  universo candidato. Si el usuario busca su código explícitamente, se responde
  con el vigente.
* Un match de confianza media o baja **nunca** se presenta como confirmado.
* Dos productos con el mismo nombre y distinta solubilidad no son el mismo
  producto: albahaca oil soluble tiene 19–21 % de aceite volátil y la
  dispersable 2–4 %.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.units import SOLUBILITY_LABELS, SpecRange
from data_layer.schema import (
    MARKER_LABELS,
    SOURCE_FIRST_CHOICE,
    STATUS_ACTIVE,
    Product,
)
from matching.normalize import similarity
from matching.spec_parser import ClientSpec

# Pesos del score. La cobertura numérica pesa más que el nombre: la
# especificación manda sobre la nomenclatura.
W_NAME = 0.35
W_SPEC = 0.40
W_ATTRS = 0.15
W_FIRST_CHOICE = 0.10

CONF_HIGH, CONF_MEDIUM, CONF_LOW = "high", "medium", "low"

CONFIDENCE_LABELS = {
    CONF_HIGH: "Alta",
    CONF_MEDIUM: "Media — revisar",
    CONF_LOW: "Baja — propuesta",
}

VERDICT_OK, VERDICT_WARN, VERDICT_FAIL = "ok", "warn", "fail"


@dataclass
class GapItem:
    """Una fila del reporte de brecha."""

    parameter: str
    requested: str
    offered: str
    verdict: str
    comment: str = ""


@dataclass
class Candidate:
    product: Product
    score: float
    confidence: str
    match_type: str
    gaps: List[GapItem] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @property
    def deviations(self) -> int:
        return sum(1 for g in self.gaps if g.verdict != VERDICT_OK)

    @property
    def blocking(self) -> int:
        return sum(1 for g in self.gaps if g.verdict == VERDICT_FAIL)

    def suggested_action(self) -> str:
        if self.blocking:
            return "Ofrecer solo con desviación aprobada por calidad"
        if self.deviations:
            return "Ofrecer con desviación documentada"
        return "Ofrecer directo"


# ---------------------------------------------------------------------------
# Puntuación
# ---------------------------------------------------------------------------

def _name_score(spec: ClientSpec, product: Product) -> float:
    target = spec.product_name or spec.family
    if not target:
        return 0.0
    score = similarity(target, product.description)
    if spec.family and product.family:
        if spec.family == product.family:
            score = max(score, 0.85)
        elif spec.family.split(",")[0] == product.family.split(",")[0]:
            score = max(score, 0.6)
    return min(score, 1.0)


def _spec_score(spec: ClientSpec, product: Product) -> Tuple[float, List[GapItem]]:
    """Cobertura de los analitos pedidos y reporte de brecha."""
    gaps: List[GapItem] = []
    if not spec.analytes:
        return 0.5, gaps  # sin exigencia numérica: neutro, ni premia ni castiga

    total = 0.0
    for name, requested in spec.analytes.items():
        offered: Optional[SpecRange] = product.analytes.get(name)
        label = MARKER_LABELS.get(name, name)

        if offered is None:
            gaps.append(
                GapItem(label, requested.format(), "—", VERDICT_WARN, "Robertet no declara este parámetro")
            )
            continue

        coverage = offered.satisfies(requested)

        if coverage >= 0.999:
            comment = ("Cumple el mínimo garantizado" if requested.kind == "min"
                       else "Rango completo dentro de lo pedido")
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_OK, comment))
        elif coverage > 0:
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_WARN,
                                "Solapa parcialmente — confirmar contra el CoA del lote"))
        else:
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_FAIL,
                                "Fuera del rango pedido"))
        total += coverage

    return total / len(spec.analytes), gaps


def _attribute_score(spec: ClientSpec, product: Product) -> Tuple[float, List[GapItem]]:
    gaps: List[GapItem] = []
    checks: List[float] = []

    if spec.solubility != "unknown":
        want = SOLUBILITY_LABELS[spec.solubility]
        have = SOLUBILITY_LABELS.get(product.solubility, "—")
        if product.solubility == spec.solubility:
            checks.append(1.0)
            gaps.append(GapItem("Solubilidad", want, have, VERDICT_OK))
        elif product.solubility == "unknown":
            checks.append(0.4)
            gaps.append(GapItem("Solubilidad", want, "—", VERDICT_WARN, "No declarada en el catálogo"))
        else:
            checks.append(0.0)
            gaps.append(
                GapItem("Solubilidad", want, have, VERDICT_FAIL,
                        "Presentación distinta: el factor de reemplazo no es comparable")
            )

    attribute_map = {
        "kosher": ("Kosher", product.kosher),
        "halal": ("Halal", product.halal),
        "vegan": ("Vegano", product.vegan),
        "gmo_free": ("No GMO", product.gmo_free),
        "organic": ("Orgánico", product.organic or None),
    }
    for key, (label, value) in attribute_map.items():
        if not spec.requirements.get(key):
            continue
        if value is True:
            checks.append(1.0)
            gaps.append(GapItem(label, "Requerido", "Sí", VERDICT_OK))
        elif value is False:
            checks.append(0.0)
            gaps.append(GapItem(label, "Requerido", "No", VERDICT_FAIL))
        else:
            checks.append(0.4)
            gaps.append(GapItem(label, "Requerido", "—", VERDICT_WARN, "Sin dato en el catálogo"))

    if spec.requirements.get("no_soy"):
        if product.contains_soy is True:
            checks.append(0.0)
            gaps.append(GapItem("Soya", "Sin soya", "Contiene aceite de soya", VERDICT_FAIL))
        elif product.contains_soy is False:
            checks.append(1.0)
            gaps.append(GapItem("Soya", "Sin soya", "No contiene", VERDICT_OK))
        else:
            checks.append(0.4)
            gaps.append(GapItem("Soya", "Sin soya", "—", VERDICT_WARN, "Sin dato en el catálogo"))

    if spec.shelf_life_min:
        have = product.shelf_life_months
        want = f"≥ {spec.shelf_life_min:g} meses"
        if have is None:
            checks.append(0.4)
            gaps.append(GapItem("Vida de anaquel", want, "—", VERDICT_WARN, "Sin dato en el catálogo"))
        elif have >= spec.shelf_life_min:
            checks.append(1.0)
            gaps.append(GapItem("Vida de anaquel", want, f"{have:g} meses", VERDICT_OK))
        else:
            checks.append(0.0)
            gaps.append(
                GapItem("Vida de anaquel", want, f"{have:g} meses", VERDICT_WARN,
                        "Confirmar propuesta de extensión con calidad")
            )

    return (sum(checks) / len(checks) if checks else 0.5), gaps


def _confidence(score: float, spec_coverage: float, candidate_gaps: List[GapItem]) -> str:
    if any(g.verdict == VERDICT_FAIL for g in candidate_gaps):
        return CONF_LOW
    if score >= 0.80 and spec_coverage >= 0.85:
        return CONF_HIGH
    if score >= 0.55:
        return CONF_MEDIUM
    return CONF_LOW


def score_product(spec: ClientSpec, product: Product) -> Candidate:
    name_score = _name_score(spec, product)
    spec_coverage, spec_gaps = _spec_score(spec, product)
    attr_score, attr_gaps = _attribute_score(spec, product)

    total = (
        W_NAME * name_score
        + W_SPEC * spec_coverage
        + W_ATTRS * attr_score
        + (W_FIRST_CHOICE if product.source == SOURCE_FIRST_CHOICE else 0.0)
    )

    gaps = spec_gaps + attr_gaps
    penalty = 0.12 * sum(1 for g in gaps if g.verdict == VERDICT_FAIL)
    total = max(0.0, min(total - penalty, 1.0))

    reasons: List[str] = []
    if product.source == SOURCE_FIRST_CHOICE:
        reasons.append("Está en la lista First Choice")
    if spec.family and product.family == spec.family:
        reasons.append("Misma familia botánica")
    if spec_coverage >= 0.999 and spec.analytes:
        reasons.append("Cubre toda la especificación numérica")

    match_type = "familia"
    if name_score >= 0.95:
        match_type = "nombre exacto"
    elif name_score >= 0.7:
        match_type = "sinónimo"
    elif name_score > 0:
        match_type = "difuso"

    return Candidate(
        product=product,
        score=total,
        confidence=_confidence(total, spec_coverage, gaps),
        match_type=match_type,
        gaps=gaps,
        reasons=reasons,
    )


def recommend(spec: ClientSpec, catalog, *, limit: int = 5) -> List[Candidate]:
    """Devuelve los mejores candidatos ofertables, First Choice primero."""
    if spec.is_empty:
        return []

    universe = [p for p in catalog.products if p.status == STATUS_ACTIVE]

    if spec.family:
        same_family = [p for p in universe if p.family == spec.family]
        if len(same_family) < 3:
            root = spec.family.split(",")[0].strip()
            same_family = [p for p in universe if p.family.split(",")[0].strip() == root]
        if same_family:
            universe = same_family

    scored = [score_product(spec, p) for p in universe]
    scored = [c for c in scored if c.score > 0.15]
    scored.sort(
        key=lambda c: (
            round(c.score, 4),
            c.product.source == SOURCE_FIRST_CHOICE,  # desempata a favor de First Choice
            len(c.product.analytes),
        ),
        reverse=True,
    )
    return scored[:limit]


# ---------------------------------------------------------------------------
# Búsqueda por código
# ---------------------------------------------------------------------------

@dataclass
class CodeLookup:
    code: str
    product: Optional[Product]
    replacement: Optional[Product] = None
    message: str = ""

    @property
    def found(self) -> bool:
        return self.product is not None


def lookup_code(code: str, catalog) -> CodeLookup:
    """Busca un código Robertet y resuelve la cadena de reemplazos.

    Si el código está anulado o reemplazado, se responde con el vigente en vez
    de devolver el obsoleto en silencio.
    """
    product = catalog.by_code(code)
    if product is None:
        return CodeLookup(code=code, product=None, message="Código no encontrado en el catálogo.")

    if product.status == STATUS_ACTIVE:
        return CodeLookup(code=code, product=product)

    replacement, seen = None, {product.code.upper()}
    cursor = product
    while cursor is not None and cursor.converted_to:
        nxt = catalog.by_code(cursor.converted_to)
        if nxt is None or nxt.code.upper() in seen:
            break
        seen.add(nxt.code.upper())
        cursor = nxt
        if cursor.status == STATUS_ACTIVE:
            replacement = cursor
            break

    if product.status == "void":
        message = f"{product.code} está marcado Void / Do Not Sample en el ASKRC. No ofrecer."
    else:
        message = f"{product.code} fue reemplazado por {product.converted_to or 'otro código'}."

    return CodeLookup(code=code, product=product, replacement=replacement, message=message)


def lookup_competitor(query: str, catalog) -> List[Tuple[object, Optional[Product]]]:
    """Busca en el mapa Kalsec / Mane por código o descripción."""
    needle = (query or "").strip().lower()
    if not needle:
        return []

    out: List[Tuple[object, Optional[Product]]] = []
    for entry in getattr(catalog, "competitors", []) or []:
        haystack = f"{entry.competitor_code} {entry.competitor_desc} {entry.competitor}".lower()
        if needle in haystack or similarity(needle, entry.competitor_desc) > 0.75:
            out.append((entry, catalog.by_code(entry.robertet_code) if entry.robertet_code else None))
    return out
