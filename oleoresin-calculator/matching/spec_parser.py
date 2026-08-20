"""Extrae requisitos estructurados de la especificación que manda el cliente.

Las specs llegan como PDF, Excel o texto pegado, en inglés o español, con
formatos como "Piperine: 35% min", "Colour value 40,000-60,000 CU",
"oil soluble", "Kosher certified", "non-GMO", "shelf life 18 months".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.units import SpecRange, normalize_solubility, parse_spec_value
from matching.normalize import detect_family, normalize

_NUM = r"\d+(?:[.,]\d+)*"

#: Etiqueta de analito en la spec -> nombre canónico.
_ANALYTE_TERMS = (
    (r"piperin[ae]", "piperine"),
    (r"curcumin[oa]?s?|curcumina", "curcumin"),
    (r"carnosic|carn[oó]sico", "carnosic_acid"),
    (r"scoville|shu\b", "scoville"),
    (r"capsaicin|capsaicina", "capsaicin"),
    (r"colou?r\s*(?:value|units?)?|valor\s*de\s*color|astas?\b", "colour"),
    (r"vanillin|vainillina", "vanillin"),
    (r"volatile\s*oil|aceite\s*vol[aá]til|essential\s*oil\s*content|\bvo\b", "volatile_oil"),
)

_REQUIREMENT_TERMS = {
    "kosher": r"kosher",
    "halal": r"halal",
    "vegan": r"vegan|vegano",
    "gmo_free": r"non[\s-]?gmo|gmo[\s-]?free|sin\s*(?:omg|transg[eé]nicos)|libre\s*de\s*gmo",
    "organic": r"\borganic\b|\borg[aá]nico\b",
    "no_soy": r"(?:no|without|sin|free\s*of|free\s*from)\s+soy|soy[\s-]?free|sin\s*soya",
    "allergen_free": r"allergen[\s-]?free|libre\s*de\s*al[eé]rgenos",
}


@dataclass
class ClientSpec:
    """Lo que el cliente pide, ya estructurado."""

    raw_text: str = ""
    family: str = ""
    product_name: str = ""
    solubility: str = "unknown"
    analytes: Dict[str, SpecRange] = field(default_factory=dict)
    requirements: Dict[str, bool] = field(default_factory=dict)
    shelf_life_min: Optional[float] = None
    competitor_code: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.family or self.analytes or self.solubility != "unknown")

    def summary(self) -> str:
        bits: List[str] = []
        if self.product_name:
            bits.append(self.product_name)
        elif self.family:
            bits.append(self.family.title())
        if self.solubility != "unknown":
            from core.units import SOLUBILITY_LABELS

            bits.append(SOLUBILITY_LABELS[self.solubility])
        from data_layer.schema import MARKER_LABELS

        for name, rng in self.analytes.items():
            bits.append(f"{MARKER_LABELS.get(name, name)} {rng.format()}")
        for key, wanted in self.requirements.items():
            if wanted:
                bits.append(_REQUIREMENT_LABELS.get(key, key))
        if self.shelf_life_min:
            bits.append(f"vida útil ≥ {self.shelf_life_min:g} meses")
        return " · ".join(bits) if bits else "sin requisitos reconocidos"


_REQUIREMENT_LABELS = {
    "kosher": "Kosher",
    "halal": "Halal",
    "vegan": "Vegano",
    "gmo_free": "No GMO",
    "organic": "Orgánico",
    "no_soy": "Sin soya",
    "allergen_free": "Libre de alérgenos",
}


def parse(text: str) -> ClientSpec:
    """Interpreta el texto libre de una especificación."""
    if not text:
        return ClientSpec()

    raw = re.sub(r"[ \t]+", " ", str(text))
    flat = re.sub(r"\s+", " ", raw)
    lowered = flat.lower()

    spec = ClientSpec(raw_text=raw)
    spec.family = detect_family(flat)
    spec.product_name = _guess_product_name(raw) or ""

    # --- solubilidad ---------------------------------------------------
    for pattern, value in (
        (r"water[\s-]?dispersib|dispersable\s*en\s*agua|\bwd\b", "water_dispersible"),
        (r"water[\s-]?solubl|soluble\s*en\s*agua|\bws\b", "water_soluble"),
        (r"oil[\s-]?solubl|soluble\s*en\s*aceite|\bos\b", "oil"),
        (r"\bemulsion", "emulsion"),
        (r"\bpowder\b|\bpolvo\b", "powder"),
    ):
        if re.search(pattern, lowered):
            spec.solubility = normalize_solubility(value)
            break

    # --- analitos ------------------------------------------------------
    for pattern, analyte in _ANALYTE_TERMS:
        if analyte in spec.analytes:
            continue
        rng = _find_value_near(raw, pattern, analyte)
        if rng is not None:
            spec.analytes[analyte] = rng

    # --- requisitos ----------------------------------------------------
    for key, pattern in _REQUIREMENT_TERMS.items():
        if re.search(pattern, lowered):
            spec.requirements[key] = True

    # --- vida útil -----------------------------------------------------
    m = re.search(
        rf"(?:shelf\s*life|vida\s*(?:útil|util|de\s*anaquel))[^\d]{{0,24}}({_NUM})", lowered
    )
    if not m:
        m = re.search(rf"({_NUM})\s*(?:months?|meses)\s*(?:shelf|de\s*vida)", lowered)
    if m:
        try:
            spec.shelf_life_min = float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    # --- código de competidor -----------------------------------------
    m = re.search(r"\b(?:kalsec|mane)\b[^\w]{0,6}([\w.\-]+)", lowered)
    if m:
        spec.competitor_code = m.group(1).strip(" .")

    return spec


def _find_value_near(text: str, term_pattern: str, analyte: str) -> Optional[SpecRange]:
    """Busca el valor numérico asociado a una etiqueta de analito.

    Acepta la etiqueta antes ("Piperine: 35 % min") o después del valor
    ("35 % min piperine"), y no cruza saltos de línea para no capturar el valor
    del renglón siguiente.
    """
    # El patrón se agrupa: sin (?:…) la alternancia se traga el resto de la
    # expresión y "Volatile oil: 15% min" captura el valor del renglón anterior.
    term = rf"(?:{term_pattern})"

    tail = rf"{term}\s*[:=\-–]?\s*(?P<v>[^\n;|]{{0,48}})"
    for match in re.finditer(tail, text, re.I):
        rng = parse_spec_value(match.group("v"), analyte=analyte)
        if rng is not None:
            return rng

    head = rf"(?P<v>[^\n;|]{{0,32}}?)\s*{term}"
    for match in re.finditer(head, text, re.I):
        rng = parse_spec_value(match.group("v"), analyte=analyte)
        if rng is not None:
            return rng
    return None


def _guess_product_name(text: str) -> Optional[str]:
    """La primera línea suele ser el nombre del producto."""
    for line in text.splitlines():
        line = line.strip(" -•\t")
        if len(line) < 3:
            continue
        if re.search(r"oleoresin|oleorresina|extract|extracto|oil|aceite|powder|polvo", line, re.I):
            return re.sub(r"\s+", " ", line)[:90]
        return re.sub(r"\s+", " ", line)[:90]
    return None


# --------------------------------------------------------------------------
# Lectura de archivos
# --------------------------------------------------------------------------

def read_upload(name: str, data: bytes) -> str:
    """Extrae texto plano de un archivo subido (PDF, Excel, CSV o texto)."""
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""

    if suffix == "pdf":
        return _read_pdf(data)
    if suffix in {"xlsx", "xlsm", "xls"}:
        return _read_excel(data)
    if suffix in {"csv", "tsv"}:
        return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def _read_pdf(data: bytes) -> str:
    try:
        import io

        import pdfplumber

        chunks: List[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:12]:
                chunks.append(page.extract_text() or "")
                for table in page.extract_tables() or []:
                    for row in table:
                        chunks.append(" | ".join(c or "" for c in row))
        return "\n".join(chunks)
    except Exception as exc:  # pragma: no cover - depende del archivo
        return f"[No se pudo leer el PDF: {exc}]"


def _read_excel(data: bytes) -> str:
    try:
        import io

        import pandas as pd

        chunks: List[str] = []
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
        for name, frame in sheets.items():
            chunks.append(f"# {name}")
            for _, row in frame.head(200).iterrows():
                cells = [str(c) for c in row.tolist() if c is not None and str(c) != "nan"]
                if cells:
                    chunks.append(" | ".join(cells))
        return "\n".join(chunks)
    except Exception as exc:  # pragma: no cover
        return f"[No se pudo leer el Excel: {exc}]"
