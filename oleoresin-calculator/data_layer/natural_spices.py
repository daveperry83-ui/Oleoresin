"""Concentración del marcador en la especia natural molida.

La versión anterior traía estos números incrustados en el código, sin fuente ni
rango. La primera pregunta de un cliente técnico es "¿de dónde sale ese 40 %?"
y no había respuesta. Aquí cada valor lleva rango y referencia, y el usuario
siempre puede sobrescribirlo con el CoA real de su materia prima.

Correcciones respecto a la tabla anterior:

* **Vainilla** declaraba oleorresina al 25 % de vainillina. No existe
  comercialmente: la vaina curada ronda 1.5–3 % y el extracto concentrado 1–6 %.
  Con aquel dato la app prometía un ahorro imposible de entregar.
* **Chile** usaba 40,000 SHU como punto fijo. El chile deshidratado comercial
  va de 15,000 a 50,000 según variedad; ahora es un rango.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class NaturalSpice:
    family: str
    label_es: str
    label_en: str
    marker: str
    unit: str
    typical: float
    low: float
    high: float
    source_es: str
    source_en: str

    def label(self, language: str = "es") -> str:
        return self.label_es if language == "es" else self.label_en

    def source(self, language: str = "es") -> str:
        return self.source_es if language == "es" else self.source_en

    def range_text(self) -> str:
        if self.high >= 1000:
            return f"{self.low:,.0f} – {self.high:,.0f} {self.unit}"
        return f"{self.low:g} – {self.high:g} {self.unit}"


_DATA: List[NaturalSpice] = [
    NaturalSpice("pepper, black and green", "Pimienta negra", "Black pepper", "piperine", "%", 5.0, 4.0, 7.0, "Contenido de piperina en baya seca, literatura de composición de especias", "Piperine content in dried berry, spice composition literature"),
    NaturalSpice("pepper, white", "Pimienta blanca", "White pepper", "piperine", "%", 6.0, 4.5, 8.0, "Contenido de piperina en baya seca descascarada", "Piperine content in husked dried berry"),
    NaturalSpice("capsicum", "Chile deshidratado", "Dried chilli", "scoville", "SHU", 30000.0, 15000.0, 50000.0, "Rango amplio según variedad; confirmar con CoA del lote", "Wide range by variety; confirm with batch CoA"),
    NaturalSpice("paprika", "Pimentón molido", "Ground paprika", "colour", "CU", 130.0, 100.0, 160.0, "Valor ASTA para pimentón molido comercial", "ASTA value for ground commercial paprika"),
    NaturalSpice("turmeric", "Cúrcuma molida", "Ground turmeric", "curcumin", "%", 3.0, 2.0, 5.0, "Curcuminoides en rizoma seco", "Curcuminoids in dried rhizome"),
    NaturalSpice("rosemary", "Romero seco", "Dried rosemary", "carnosic_acid", "%", 2.0, 1.0, 3.5, "Ácido carnósico en hoja seca; muy dependiente del origen", "Carnosic acid in dried leaf; highly dependent on origin"),
    NaturalSpice("ginger", "Jengibre seco", "Dried ginger", "volatile_oil", "%", 2.0, 1.5, 3.0, "Aceite volátil en rizoma seco", "Volatile oil in dried rhizome"),
    NaturalSpice("cardamom", "Cardamomo", "Cardamom", "volatile_oil", "%", 6.5, 4.0, 8.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("clove", "Clavo", "Clove", "volatile_oil", "%", 16.0, 15.0, 20.0, "Aceite volátil en botón floral seco", "Volatile oil in dried floral bud"),
    NaturalSpice("nutmeg", "Nuez moscada", "Nutmeg", "volatile_oil", "%", 8.0, 6.0, 11.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("mace", "Macis", "Mace", "volatile_oil", "%", 10.0, 7.0, 14.0, "Aceite volátil en arilo", "Volatile oil in aril"),
    NaturalSpice("cassia", "Canela / casia", "Cinnamon / cassia", "volatile_oil", "%", 1.5, 1.0, 4.0, "Aceite volátil en corteza", "Volatile oil in bark"),
    NaturalSpice("allspice", "Pimienta gorda", "Allspice", "volatile_oil", "%", 4.0, 3.0, 5.0, "Aceite volátil en baya seca", "Volatile oil in dried berry"),
    NaturalSpice("bay", "Laurel", "Bay leaf", "volatile_oil", "%", 2.0, 1.0, 3.0, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("cumin", "Comino", "Cumin", "volatile_oil", "%", 3.0, 2.5, 4.5, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("coriander", "Cilantro (semilla)", "Coriander seed", "volatile_oil", "%", 0.8, 0.4, 1.2, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("caraway", "Alcaravea", "Caraway", "volatile_oil", "%", 4.0, 3.0, 6.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("fennel", "Hinojo", "Fennel", "volatile_oil", "%", 4.0, 2.0, 6.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("anise", "Anís", "Anise", "volatile_oil", "%", 2.5, 2.0, 3.5, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("dill", "Eneldo", "Dill seed", "volatile_oil", "%", 3.0, 2.0, 4.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("celery", "Semilla de apio", "Celery seed", "volatile_oil", "%", 2.5, 1.5, 3.0, "Aceite volátil en semilla", "Volatile oil in seed"),
    NaturalSpice("garlic", "Ajo deshidratado", "Dried garlic", "volatile_oil", "%", 0.3, 0.2, 0.4, "Compuestos de azufre volátiles en ajo deshidratado", "Volatile sulfur compounds in dried garlic"),
    NaturalSpice("onion", "Cebolla deshidratada", "Dried onion", "volatile_oil", "%", 0.07, 0.03, 0.10, "Compuestos de azufre volátiles en cebolla deshidratada", "Volatile sulfur compounds in dried onion"),
    NaturalSpice("basil", "Albahaca seca", "Dried basil", "volatile_oil", "%", 0.6, 0.4, 1.0, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("oregano", "Orégano seco", "Dried oregano", "volatile_oil", "%", 2.5, 1.5, 4.0, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("thyme", "Tomillo seco", "Dried thyme", "volatile_oil", "%", 1.5, 1.0, 2.5, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("sage", "Salvia seca", "Dried sage", "volatile_oil", "%", 1.5, 1.0, 2.8, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("marjoram", "Mejorana", "Marjoram", "volatile_oil", "%", 1.5, 0.7, 3.0, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("parsley", "Perejil seco", "Dried parsley", "volatile_oil", "%", 0.3, 0.1, 0.5, "Aceite volátil en hoja seca", "Volatile oil in dried leaf"),
    NaturalSpice("mustard", "Mostaza", "Mustard", "volatile_oil", "%", 1.0, 0.5, 1.5, "Aceite volátil (isotiocianatos) en semilla", "Volatile oil (isothiocyanates) in seed"),
    # Nota: la oleorresina de vainilla al 25 % de vainillina no existe comercialmente
    NaturalSpice("vanilla", "Vaina de vainilla curada", "Cured vanilla bean", "vanillin", "%", 2.0, 1.5, 3.0, "Vainillina en vaina curada; el extracto concentrado varía 1–6 %, no 25 %", "Vanillin in cured bean; concentrated extract ranges 1–6%, not 25%"),
    NaturalSpice("annatto", "Achiote (semilla)", "Annatto seed", "colour", "CU", 250.0, 150.0, 400.0, "Bixina expresada como valor de color; confirmar método", "Bixin expressed as color value; confirm method"),
]

_BY_FAMILY: Dict[str, NaturalSpice] = {s.family: s for s in _DATA}


def get(family: str) -> Optional[NaturalSpice]:
    if not family:
        return None
    if family in _BY_FAMILY:
        return _BY_FAMILY[family]
    root = family.split(",")[0].strip()
    for key, spice in _BY_FAMILY.items():
        if key.split(",")[0].strip() == root:
            return spice
    return None


def for_marker(family: str, marker: str) -> Optional[NaturalSpice]:
    """La referencia solo aplica si el marcador coincide."""
    spice = get(family)
    if spice is None:
        return None
    if marker and spice.marker != marker:
        return None
    return spice


def all_spices() -> List[NaturalSpice]:
    return list(_DATA)
