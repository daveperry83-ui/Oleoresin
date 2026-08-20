"""Normalización de nombres y sinónimos bilingües.

El mismo botánico aparece como nombre común en inglés, en español, botánico o
comercial. El cruce español/inglés está siempre activo porque los RFQs de LATAM
llegan mezclados.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, Set

#: familia canónica -> alias (es / en / pt / zh / hi / botánico / comercial)
SYNONYMS: Dict[str, Set[str]] = {
    "allspice": {"allspice", "pimento", "pimienta gorda", "pimienta dulce", "pimenta", "pimenta jamaica", "pimenta da jamaica"},
    "anise": {"anise", "anis", "aniseed", "anethole", "pimpinella anisum", "anis", "anisado", "estrela de anis", "茴香", "八角"},
    "annatto": {"annatto", "achiote", "bixa orellana", "bixin", "norbixin", "urucum", "colorau"},
    "basil": {"basil", "albahaca", "ocimum basilicum", "manjericao", "罗勒", "तुलसी"},
    "bay": {"bay", "bay leaf", "laurel", "laurus nobilis", "loureiro", "月桂叶"},
    "capsicum": {"capsicum", "chile", "chili", "aji", "cayenne", "cayena", "paprika oleoresin capsicum", "capsaicin", "pimenta", "辣椒", "काली मिर्च"},
    "caraway": {"caraway", "alcaravea", "carum carvi", "alcaravia", "香茴"},
    "cardamom": {"cardamom", "cardamomo", "elettaria cardamomum", "cardamomo", "绿豆蔻", "काली इलायची"},
    "cassia": {"cassia", "cinnamon", "canela", "cinnamomum", "cinnamaldehyde", "canela", "肉桂", "दालचीनी"},
    "celery": {"celery", "apio", "apium graveolens", "celery seed", "salsao", "芹菜", "अजवाइन"},
    "chipotle": {"chipotle", "chipotle"},
    "cilantro": {"cilantro", "coriander leaf", "culantro", "coentro", "芫荽"},
    "clove": {"clove", "clavo", "eugenol", "syzygium aromaticum", "clove bud", "cravo", "丁香", "लौंग"},
    "coriander": {"coriander", "coriandro", "semilla de cilantro", "coriandrum sativum", "coentro", "香菜籽", "धनिया"},
    "cumin": {"cumin", "comino", "cuminum cyminum", "jeera", "comino", "孜然", "जीरा"},
    "dill": {"dill", "eneldo", "anethum graveolens", "endro", "莳萝"},
    "fennel": {"fennel", "hinojo", "foeniculum vulgare", "funcho", "茴香", "सौंफ"},
    "foenugreek": {"foenugreek", "fenugreek", "fenogreco", "alholva", "trigonella", "trigonela", "葫芦巴"},
    "garlic": {"garlic", "ajo", "allium sativum", "alho", "大蒜", "लहसुन"},
    "ginger": {"ginger", "jengibre", "zingiber officinale", "gingerol", "gengibre", "生姜", "अदरक"},
    "habanero": {"habanero", "habanero"},
    "jalapeno": {"jalapeno", "jalapeño", "jalapeno", "墨西哥辣椒"},
    "juniper": {"juniper", "enebro", "juniperus", "zimbro"},
    "lovage": {"lovage", "levistico", "levisticum", "levisbaco"},
    "mace": {"mace", "macis", "myristica", "noz moscada (envoltorio)", "豆蔻衣"},
    "marjoram": {"marjoram", "mejorana", "origanum majorana", "manjerona", "墨角兰"},
    "mustard": {"mustard", "mostaza", "wasabi", "horseradish", "rabano picante", "brassica", "mostarda", "芥末", "राई"},
    "nutmeg": {"nutmeg", "nuez moscada", "myristica fragrans", "noz moscada", "肉豆蔻", "जायफल"},
    "onion": {"onion", "cebolla", "allium cepa", "cebola", "洋葱", "प्याज"},
    "oregano": {"oregano", "origanum vulgare", "oregano", "牛至", "अजवाइन के पत्ते"},
    "paprika": {"paprika", "pimenton", "pimentao", "capsicum annuum", "color value", "paprica", "辣椒粉", "पापरिका"},
    "parsley": {"parsley", "perejil", "petroselinum", "salsa", "欧芹", "अजमोद"},
    "pepper, black and green": {"black pepper", "pimienta negra", "green pepper", "pimienta verde", "piper nigrum", "piperine", "piperina", "pimenta preta", "pimenta verde", "黑胡椒", "绿胡椒", "काली मिर्च", "हरी मिर्च"},
    "pepper, white": {"white pepper", "pimienta blanca", "pimenta branca", "白胡椒", "सफेद मिर्च"},
    "rosemary": {"rosemary", "romero", "rosmarinus", "carnosic", "acido carnosico", "rosemarox", "alecrim", "迷迭香", "रोज़मेरी"},
    "sage": {"sage", "salvia", "salvia officinalis", "salva", "鼠尾草", "ऋषि"},
    "star anise": {"star anise", "anis estrella", "illicium verum", "badiana", "anis estrelado", "八角", "चक्र फूल"},
    "tarragon": {"tarragon", "estragon", "artemisia dracunculus", "estrago", "龙蒿"},
    "thyme": {"thyme", "tomillo", "thymus vulgaris", "tomilho", "百里香", "थाइम"},
    "turmeric": {"turmeric", "curcuma", "cúrcuma", "curcumin", "curcumina", "curcuma longa", "curcuma", "姜黄", "हल्दी"},
    "vanilla": {"vanilla", "vainilla", "vanillin", "vainillina", "vanilla planifolia", "baunilha", "香草", "वेनिला"},
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

def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def _tokenize(text: str):
    """Extrae tokens de texto en cualquier escritura (latín, CJK, devanagari, ...).

    ``[a-z0-9]+`` solo reconoce ASCII: descarta chino e hindi por completo. Un
    token aquí es cualquier corrida de caracteres que no sea espacio, control,
    puntuación o símbolo (categorías Unicode Z*, C*, P*, S*). Esto conserva las
    marcas combinantes espaciadas (matras devanagari, categoría Mc) como parte
    de la palabra en vez de partirla en fragmentos.
    """
    tokens = []
    current = []
    for ch in text:
        category = unicodedata.category(ch)
        if category[0] in ("Z", "C", "P", "S"):
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def normalize(text: str) -> str:
    """Minúsculas, sin acentos, abreviaturas expandidas, separadores unificados."""
    if not text:
        return ""
    lowered = strip_accents(str(text).lower())
    lowered = lowered.replace("™", " ").replace("®", " ").replace("h2oleoresin", "water dispersible oleoresin")
    tokens = _tokenize(lowered)
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
