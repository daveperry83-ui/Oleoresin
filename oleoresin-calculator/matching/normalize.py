"""Normalización de nombres y sinónimos bilingües.

El mismo botánico aparece como nombre común en inglés, en español, botánico o
comercial. El cruce español/inglés está siempre activo porque los RFQs de LATAM
llegan mezclados.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, Set

#: familia canónica -> alias (es / en / botánico / comercial)
SYNONYMS: Dict[str, Set[str]] = {
    "allspice": {"allspice", "pimento", "pimienta gorda", "pimienta dulce", "pimenta", "pimenta jamaica"},
    "anise": {"anise", "anis", "aniseed", "anethole", "pimpinella anisum"},
    "annatto": {"annatto", "achiote", "bixa orellana", "bixin", "norbixin", "urucum"},
    "basil": {"basil", "albahaca", "ocimum basilicum"},
    "bay": {"bay", "bay leaf", "laurel", "laurus nobilis"},
    "capsicum": {"capsicum", "chile", "chili", "aji", "cayenne", "cayena", "paprika oleoresin capsicum", "capsaicin"},
    "caraway": {"caraway", "alcaravea", "carum carvi"},
    "cardamom": {"cardamom", "cardamomo", "elettaria cardamomum"},
    "cassia": {"cassia", "cinnamon", "canela", "cinnamomum", "cinnamaldehyde"},
    "celery": {"celery", "apio", "apium graveolens", "celery seed"},
    "chipotle": {"chipotle"},
    "cilantro": {"cilantro", "coriander leaf", "culantro"},
    "clove": {"clove", "clavo", "eugenol", "syzygium aromaticum", "clove bud"},
    "coriander": {"coriander", "coriandro", "semilla de cilantro", "coriandrum sativum"},
    "cumin": {"cumin", "comino", "cuminum cyminum", "jeera"},
    "dill": {"dill", "eneldo", "anethum graveolens"},
    "fennel": {"fennel", "hinojo", "foeniculum vulgare"},
    "foenugreek": {"foenugreek", "fenugreek", "fenogreco", "alholva", "trigonella"},
    "garlic": {"garlic", "ajo", "allium sativum"},
    "ginger": {"ginger", "jengibre", "zingiber officinale", "gingerol"},
    "habanero": {"habanero"},
    "jalapeno": {"jalapeno", "jalapeño"},
    "juniper": {"juniper", "enebro", "juniperus"},
    "lovage": {"lovage", "levistico", "levisticum"},
    "mace": {"mace", "macis", "myristica"},
    "marjoram": {"marjoram", "mejorana", "origanum majorana"},
    "mustard": {"mustard", "mostaza", "wasabi", "horseradish", "rabano picante", "brassica"},
    "nutmeg": {"nutmeg", "nuez moscada", "myristica fragrans"},
    "onion": {"onion", "cebolla", "allium cepa"},
    "oregano": {"oregano", "origanum vulgare"},
    "paprika": {"paprika", "pimenton", "pimentao", "capsicum annuum", "color value"},
    "parsley": {"parsley", "perejil", "petroselinum"},
    "pepper, black and green": {"black pepper", "pimienta negra", "green pepper", "pimienta verde", "piper nigrum", "piperine", "piperina"},
    "pepper, white": {"white pepper", "pimienta blanca"},
    "rosemary": {"rosemary", "romero", "rosmarinus", "carnosic", "acido carnosico", "rosemarox"},
    "sage": {"sage", "salvia", "salvia officinalis"},
    "star anise": {"star anise", "anis estrella", "illicium verum", "badiana"},
    "tarragon": {"tarragon", "estragon", "artemisia dracunculus"},
    "thyme": {"thyme", "tomillo", "thymus vulgaris"},
    "turmeric": {"turmeric", "curcuma", "cúrcuma", "curcumin", "curcumina", "curcuma longa"},
    "vanilla": {"vanilla", "vainilla", "vanillin", "vainillina", "vanilla planifolia"},
}

#: Abreviaturas que aparecen en RFQs y listas internas.
ABBREVIATIONS = {
    "or": "oleoresin",
    "oleo": "oleoresin",
    "ol": "oleoresin",
    "nat": "natural",
    "ext": "extract",
    "eo": "essential oil",
    "wd": "water dispersible",
    "ws": "water soluble",
    "os": "oil soluble",
    "vo": "volatile oil",
    "conc": "concentrate",
    "pwd": "powder",
    "std": "standardized",
}

_TOKEN = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def normalize(text: str) -> str:
    """Minúsculas, sin acentos, abreviaturas expandidas, separadores unificados."""
    if not text:
        return ""
    lowered = strip_accents(str(text).lower())
    lowered = lowered.replace("™", " ").replace("®", " ").replace("h2oleoresin", "water dispersible oleoresin")
    tokens = _TOKEN.findall(lowered)
    expanded = [ABBREVIATIONS.get(token, token) for token in tokens]
    return " ".join(expanded)


def tokens(text: str) -> Set[str]:
    return set(normalize(text).split())


_ALIAS_INDEX: Dict[str, str] = {}
for _family, _aliases in SYNONYMS.items():
    for _alias in _aliases:
        _ALIAS_INDEX[normalize(_alias)] = _family
    _ALIAS_INDEX[normalize(_family)] = _family


def detect_family(text: str) -> str:
    """Deduce la familia botánica del texto libre de una spec.

    Prefiere el alias más largo para que 'black pepper' gane sobre 'pepper'.
    """
    haystack = normalize(text)
    best, best_len = "", 0
    for alias, family in _ALIAS_INDEX.items():
        if not alias:
            continue
        if re.search(rf"(?:^|\s){re.escape(alias)}(?:\s|$)", haystack) and len(alias) > best_len:
            best, best_len = family, len(alias)
    return best


def similarity(a: str, b: str) -> float:
    """Similitud 0..1 entre dos nombres normalizados.

    Usa rapidfuzz si está instalado; si no, cae a difflib. El resultado se usa
    solo para ordenar candidatos, nunca para confirmar un match por sí solo.
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    try:
        from rapidfuzz import fuzz

        return max(fuzz.token_set_ratio(na, nb), fuzz.partial_ratio(na, nb)) / 100.0
    except ImportError:
        from difflib import SequenceMatcher

        ratio = SequenceMatcher(None, na, nb).ratio()
        ta, tb = set(na.split()), set(nb.split())
        jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
        return max(ratio, jaccard)


def family_aliases(family: str) -> Iterable[str]:
    return SYNONYMS.get(family, {family})
