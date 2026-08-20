"""Ahorro por lote y costos ocultos.

El costo en uso puro subestima el valor de la oleorresina: no captura el menor
volumen de flete y almacenaje, la merma evitada ni el tratamiento microbiológico
que la especia molida sí necesita. Tampoco captura los costos reales del cambio
(equipo de dosificación, dispersión). Este módulo los hace explícitos y
auditables en vez de dejarlos como argumento verbal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.replacement import CalculationError, Replacement


@dataclass
class HiddenCosts:
    """Costos y ahorros que no están en el precio por kg.

    Todos son opcionales y por defecto valen 0: la app nunca infla un ahorro
    con supuestos que el usuario no haya tecleado.
    """

    #: Costo logístico por kg de material movido (flete + almacenaje).
    logistics_per_kg: float = 0.0
    #: % de especia natural que se pierde por manipulación y no llega al producto.
    waste_pct_natural: float = 0.0
    #: Costo por kg de tratamiento microbiológico (ETO / vapor) de la especia.
    sterilization_per_kg: float = 0.0
    #: Costo anual fijo del cambio: equipo de dosificación, dispersión, validación.
    changeover_cost: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.logistics_per_kg,
                self.waste_pct_natural,
                self.sterilization_per_kg,
                self.changeover_cost,
            )
        )


@dataclass
class BatchResult:
    natural_kg: float
    oleoresin_kg: float
    natural_cost: float
    oleoresin_cost: float
    direct_saving: float
    logistics_saving: float
    waste_saving: float
    sterilization_saving: float
    changeover_cost: float
    currency: str = "USD"

    @property
    def net_saving(self) -> float:
        return (
            self.direct_saving
            + self.logistics_saving
            + self.waste_saving
            + self.sterilization_saving
            - self.changeover_cost
        )

    @property
    def net_saving_pct(self) -> Optional[float]:
        if self.natural_cost <= 0:
            return None
        return self.net_saving / self.natural_cost * 100.0

    @property
    def volume_reduction_pct(self) -> Optional[float]:
        if self.natural_kg <= 0:
            return None
        return (1 - self.oleoresin_kg / self.natural_kg) * 100.0

    def waterfall(self) -> List[Tuple[str, float, str]]:
        """Pasos del gráfico de cascada: (etiqueta, valor, tipo)."""
        steps: List[Tuple[str, float, str]] = [
            ("Costo especia natural", self.natural_cost, "base"),
            ("Costo oleorresina", -self.oleoresin_cost, "negative"),
        ]
        if self.logistics_saving:
            steps.append(("Flete y almacenaje", self.logistics_saving, "positive"))
        if self.waste_saving:
            steps.append(("Merma evitada", self.waste_saving, "positive"))
        if self.sterilization_saving:
            steps.append(("Tratamiento microbiológico", self.sterilization_saving, "positive"))
        if self.changeover_cost:
            steps.append(("Equipo y dispersión", -self.changeover_cost, "negative"))
        steps.append(("Ahorro neto anual", self.net_saving, "total"))
        return steps


def batch(
    replacement: Replacement,
    natural_kg: float,
    hidden: Optional[HiddenCosts] = None,
) -> BatchResult:
    if natural_kg < 0:
        raise CalculationError("El volumen no puede ser negativo")
    hidden = hidden or HiddenCosts()

    oleoresin_kg = replacement.oleoresin_needed(natural_kg)
    natural_cost = natural_kg * replacement.natural_price
    oleoresin_cost = oleoresin_kg * replacement.oleoresin_price

    logistics = hidden.logistics_per_kg * (natural_kg - oleoresin_kg)
    waste = natural_kg * (hidden.waste_pct_natural / 100.0) * replacement.natural_price
    sterilization = hidden.sterilization_per_kg * natural_kg

    return BatchResult(
        natural_kg=natural_kg,
        oleoresin_kg=oleoresin_kg,
        natural_cost=natural_cost,
        oleoresin_cost=oleoresin_cost,
        direct_saving=natural_cost - oleoresin_cost,
        logistics_saving=logistics,
        waste_saving=waste,
        sterilization_saving=sterilization,
        changeover_cost=hidden.changeover_cost,
        currency=replacement.currency,
    )


#: Umbral por debajo del cual el argumento de venta deja de ser el precio.
LOW_RATIO_THRESHOLD = 4.0


def commercial_advice(replacement: Replacement) -> List[str]:
    """Notas honestas sobre cuándo el argumento NO es el costo.

    Una herramienta que solo dice "sí, ahorras" no es creíble. Para especias de
    alto contenido de volátiles (clavo, anís estrella, cardamomo) el factor de
    reemplazo es bajo y el arbitraje rara vez favorece a la oleorresina por
    precio puro — pero sí por estandarización y microbiología.
    """
    notes: List[str] = []

    if replacement.effective_ratio < LOW_RATIO_THRESHOLD:
        notes.append(
            f"El factor de reemplazo es bajo ({replacement.effective_ratio:.1f}). "
            "En especias de alto contenido de volátiles el argumento rara vez es el "
            "precio: apóyate en estandarización lote a lote, ausencia de carga "
            "microbiana y vida útil."
        )

    if not replacement.is_favourable:
        notes.append(
            "A estos precios la oleorresina sale más cara por kg equivalente. "
            "Revisa si el cliente está comparando contra una especia de grado inferior, "
            "o cambia el eje de la conversación a costo total y consistencia."
        )
    elif replacement.price_headroom > 0:
        notes.append(
            f"Tienes {replacement.price_headroom:,.2f} {replacement.currency}/kg de espacio "
            f"antes del precio de indiferencia ({replacement.indifference_price:,.2f})."
        )

    if replacement.efficiency >= 0.99 and replacement.marker == "volatile_oil":
        notes.append(
            "Estás calculando aceite volátil con eficiencia 1.00. El perfil sensorial "
            "de una oleorresina no es idéntico al de la especia molida; un factor de "
            "0.80–0.90 es lo que suele sostenerse en la prueba de planta."
        )

    return notes
