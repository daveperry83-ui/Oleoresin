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
    marker_label,
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

CONFIDENCE_LABELS_EN = {
    CONF_HIGH: "High",
    CONF_MEDIUM: "Medium — review",
    CONF_LOW: "Low — proposed",
}


def confidence_label(confidence: str, language: str = "es") -> str:
    table = CONFIDENCE_LABELS_EN if language == "en" else CONFIDENCE_LABELS
    return table.get(confidence, confidence)


#: Textos del reporte de brecha, por idioma.
_GAP_TEXT = {
    "es": {
        "not_declared": "Robertet no declara este parámetro",
        "meets_minimum": "Cumple el mínimo garantizado",
        "full_range": "Rango completo dentro de lo pedido",
        "partial_overlap": "Solapa parcialmente — confirmar contra el CoA del lote",
        "out_of_range": "Fuera del rango pedido",
        "solubility": "Solubilidad",
        "not_in_catalog": "No declarada en el catálogo",
        "different_form": "Presentación distinta: el factor de reemplazo no es comparable",
        "kosher": "Kosher",
        "halal": "Halal",
        "vegan": "Vegano",
        "non_gmo": "No GMO",
        "organic": "Orgánico",
        "required": "Requerido",
        "yes": "Sí",
        "no": "No",
        "no_catalog_data": "Sin dato en el catálogo",
        "soy": "Soya",
        "no_soy": "Sin soya",
        "contains_soy_oil": "Contiene aceite de soya",
        "does_not_contain": "No contiene",
        "shelf_life": "Vida de anaquel",
        "months": "meses",
        "confirm_extension": "Confirmar propuesta de extensión con calidad",
        "first_choice": "Está en la lista First Choice",
        "same_family": "Misma familia botánica",
        "covers_all_spec": "Cubre toda la especificación numérica",
        "family": "familia",
        "exact_name": "nombre exacto",
        "synonym": "sinónimo",
        "fuzzy": "difuso",
        "offer_with_approved_deviation": "Ofrecer solo con desviación aprobada por calidad",
        "offer_with_documented_deviation": "Ofrecer con desviación documentada",
        "offer_direct": "Ofrecer directo",
    },
    "en": {
        "not_declared": "Robertet does not declare this parameter",
        "meets_minimum": "Meets the guaranteed minimum",
        "full_range": "Full range within what was requested",
        "partial_overlap": "Partially overlaps — confirm against the batch CoA",
        "out_of_range": "Outside the requested range",
        "solubility": "Solubility",
        "not_in_catalog": "Not declared in the catalogue",
        "different_form": "Different form: the replacement factor is not comparable",
        "kosher": "Kosher",
        "halal": "Halal",
        "vegan": "Vegan",
        "non_gmo": "Non GMO",
        "organic": "Organic",
        "required": "Required",
        "yes": "Yes",
        "no": "No",
        "no_catalog_data": "No data in the catalogue",
        "soy": "Soy",
        "no_soy": "Soy-free",
        "contains_soy_oil": "Contains soy oil",
        "does_not_contain": "Does not contain",
        "shelf_life": "Shelf life",
        "months": "months",
        "confirm_extension": "Confirm extension proposal with quality",
        "first_choice": "It's on the First Choice list",
        "same_family": "Same botanical family",
        "covers_all_spec": "Covers the whole numeric specification",
        "family": "family",
        "exact_name": "exact name",
        "synonym": "synonym",
        "fuzzy": "fuzzy",
        "offer_with_approved_deviation": "Offer only with quality-approved deviation",
        "offer_with_documented_deviation": "Offer with documented deviation",
        "offer_direct": "Offer directly",
    },
}


def _gt(language: str, key: str) -> str:
    table = _GAP_TEXT.get(language, _GAP_TEXT["es"])
    return table.get(key, _GAP_TEXT["es"].get(key, key))

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

    def suggested_action(self, language: str = "es") -> str:
        if self.blocking:
            return _gt(language, "offer_with_approved_deviation")
        if self.deviations:
            return _gt(language, "offer_with_documented_deviation")
        return _gt(language, "offer_direct")


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


def _spec_score(spec: ClientSpec, product: Product, language: str = "es") -> Tuple[float, List[GapItem]]:
    """Cobertura de los analitos pedidos y reporte de brecha."""
    gaps: List[GapItem] = []
    if not spec.analytes:
        return 0.5, gaps  # sin exigencia numérica: neutro, ni premia ni castiga

    total = 0.0
    for name, requested in spec.analytes.items():
        offered: Optional[SpecRange] = product.analytes.get(name)
        label = marker_label(name, language)

        if offered is None:
            gaps.append(
                GapItem(label, requested.format(), "—", VERDICT_WARN, _gt(language, "not_declared"))
            )
            continue

        coverage = offered.satisfies(requested)

        if coverage >= 0.999:
            comment = (_gt(language, "meets_minimum") if requested.kind == "min"
                       else _gt(language, "full_range"))
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_OK, comment))
        elif coverage > 0:
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_WARN,
                                _gt(language, "partial_overlap")))
        else:
            gaps.append(GapItem(label, requested.format(), offered.format(), VERDICT_FAIL,
                                _gt(language, "out_of_range")))
        total += coverage

    return total / len(spec.analytes), gaps


def _attribute_score(spec: ClientSpec, product: Product, language: str = "es") -> Tuple[float, List[GapItem]]:
    gaps: List[GapItem] = []
    checks: List[float] = []
    solubility_label = _gt(language, "solubility")

    if spec.solubility != "unknown":
        want = SOLUBILITY_LABELS[spec.solubility]
        have = SOLUBILITY_LABELS.get(product.solubility, "—")
        if product.solubility == spec.solubility:
            checks.append(1.0)
            gaps.append(GapItem(solubility_label, want, have, VERDICT_OK))
        elif product.solubility == "unknown":
            checks.append(0.4)
            gaps.append(GapItem(solubility_label, want, "—", VERDICT_WARN, _gt(language, "not_in_catalog")))
        else:
            checks.append(0.0)
            gaps.append(
                GapItem(solubility_label, want, have, VERDICT_FAIL, _gt(language, "different_form"))
            )

    attribute_map = {
        "kosher": (_gt(language, "kosher"), product.kosher),
        "halal": (_gt(language, "halal"), product.halal),
        "vegan": (_gt(language, "vegan"), product.vegan),
        "gmo_free": (_gt(language, "non_gmo"), product.gmo_free),
        "organic": (_gt(language, "organic"), product.organic or None),
    }
    required_label = _gt(language, "required")
    yes_label = _gt(language, "yes")
    no_label = _gt(language, "no")
    no_catalog_data = _gt(language, "no_catalog_data")
    for key, (label, value) in attribute_map.items():
        if not spec.requirements.get(key):
            continue
        if value is True:
            checks.append(1.0)
            gaps.append(GapItem(label, required_label, yes_label, VERDICT_OK))
        elif value is False:
            checks.append(0.0)
            gaps.append(GapItem(label, required_label, no_label, VERDICT_FAIL))
        else:
            checks.append(0.4)
            gaps.append(GapItem(label, required_label, "—", VERDICT_WARN, no_catalog_data))

    if spec.requirements.get("no_soy"):
        soy_label = _gt(language, "soy")
        no_soy_label = _gt(language, "no_soy")
        if product.contains_soy is True:
            checks.append(0.0)
            gaps.append(GapItem(soy_label, no_soy_label, _gt(language, "contains_soy_oil"), VERDICT_FAIL))
        elif product.contains_soy is False:
            checks.append(1.0)
            gaps.append(GapItem(soy_label, no_soy_label, _gt(language, "does_not_contain"), VERDICT_OK))
        else:
            checks.append(0.4)
            gaps.append(GapItem(soy_label, no_soy_label, "—", VERDICT_WARN, no_catalog_data))

    if spec.shelf_life_min:
        have = product.shelf_life_months
        months_label = _gt(language, "months")
        shelf_life_label = _gt(language, "shelf_life")
        want = f"≥ {spec.shelf_life_min:g} {months_label}"
        if have is None:
            checks.append(0.4)
            gaps.append(GapItem(shelf_life_label, want, "—", VERDICT_WARN, no_catalog_data))
        elif have >= spec.shelf_life_min:
            checks.append(1.0)
            gaps.append(GapItem(shelf_life_label, want, f"{have:g} {months_label}", VERDICT_OK))
        else:
            checks.append(0.0)
            gaps.append(
                GapItem(shelf_life_label, want, f"{have:g} {months_label}", VERDICT_WARN,
                        _gt(language, "confirm_extension"))
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


def score_product(spec: ClientSpec, product: Product, language: str = "es") -> Candidate:
    name_score = _name_score(spec, product)
    spec_coverage, spec_gaps = _spec_score(spec, product, language)
    attr_score, attr_gaps = _attribute_score(spec, product, language)

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
        reasons.append(_gt(language, "first_choice"))
    if spec.family and product.family == spec.family:
        reasons.append(_gt(language, "same_family"))
    if spec_coverage >= 0.999 and spec.analytes:
        reasons.append(_gt(language, "covers_all_spec"))

    match_type = _gt(language, "family")
    if name_score >= 0.95:
        match_type = _gt(language, "exact_name")
    elif name_score >= 0.7:
        match_type = _gt(language, "synonym")
    elif name_score > 0:
        match_type = _gt(language, "fuzzy")

    return Candidate(
        product=product,
        score=total,
        confidence=_confidence(total, spec_coverage, gaps),
        match_type=match_type,
        gaps=gaps,
        reasons=reasons,
    )


def recommend(spec: ClientSpec, catalog, *, limit: int = 5, language: str = "es") -> List[Candidate]:
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

    scored = [score_product(spec, p, language) for p in universe]
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


def lookup_code(code: str, catalog, language: str = "es") -> CodeLookup:
    """Busca un código Robertet y resuelve la cadena de reemplazos.

    Si el código está anulado o reemplazado, se responde con el vigente en vez
    de devolver el obsoleto en silencio.
    """
    en = language == "en"
    product = catalog.by_code(code)
    if product is None:
        not_found = "Code not found in the catalogue." if en else "Código no encontrado en el catálogo."
        return CodeLookup(code=code, product=None, message=not_found)

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
        message = (f"{product.code} is marked Void / Do Not Sample in the ASKRC. Do not offer." if en
                   else f"{product.code} está marcado Void / Do Not Sample en el ASKRC. No ofrecer.")
    else:
        other_code = "another code" if en else "otro código"
        verb = "was replaced by" if en else "fue reemplazado por"
        message = f"{product.code} {verb} {product.converted_to or other_code}."

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
