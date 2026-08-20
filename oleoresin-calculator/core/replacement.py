"""Factor de reemplazo, costo en uso y precio de indiferencia.

El cálculo teórico ``ratio = c_oleo / c_nat`` es estequiometría pura del
marcador. Es exacto cuando el atributo que el cliente compra *es* el marcador
(color en CU, pungencia en SHU). Para aceite volátil no lo es: la extracción
pierde top notes y aporta resinas no volátiles, así que el factor de uso real
queda por debajo del teórico. De ahí el factor de eficiencia.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class Replacement:
    """Resultado del cálculo de reemplazo para un par especia/oleorresina."""

    marker: str
    natural_concentration: float
    oleoresin_concentration: float
    efficiency: float
    oleoresin_price: float
    natural_price: float
    currency: str = "USD"

    # ------------------------------------------------------------- factores
    @property
    def theoretical_ratio(self) -> float:
        """kg de especia natural que reemplaza 1 kg de oleorresina, sin ajuste."""
        return self.oleoresin_concentration / self.natural_concentration

    @property
    def effective_ratio(self) -> float:
        """El factor que se le promete al cliente."""
        return self.theoretical_ratio * self.efficiency

    # -------------------------------------------------------------- economía
    @property
    def cost_in_use(self) -> float:
        """Costo de la oleorresina por kg de especia natural equivalente."""
        return self.oleoresin_price / self.effective_ratio

    @property
    def saving_per_kg(self) -> float:
        """Positivo = la oleorresina sale más barata."""
        return self.natural_price - self.cost_in_use

    @property
    def saving_pct(self) -> Optional[float]:
        if self.natural_price <= 0:
            return None
        return self.saving_per_kg / self.natural_price * 100.0

    @property
    def indifference_price(self) -> float:
        """Precio máximo de la oleorresina antes de perder la ventaja.

        El número más útil de toda la herramienta para negociar: cuánto espacio
        de precio queda por encima del precio actual.
        """
        return self.natural_price * self.effective_ratio

    @property
    def price_headroom(self) -> float:
        return self.indifference_price - self.oleoresin_price

    @property
    def is_favourable(self) -> bool:
        return self.saving_per_kg > 0

    def oleoresin_needed(self, natural_kg: float) -> float:
        if natural_kg < 0:
            raise CalculationError("El volumen no puede ser negativo")
        return natural_kg / self.effective_ratio


def build(
    *,
    marker: str,
    natural_concentration: float,
    oleoresin_concentration: float,
    oleoresin_price: float,
    natural_price: float,
    efficiency: float = 1.0,
    currency: str = "USD",
) -> Replacement:
    """Valida las entradas y devuelve el cálculo.

    Se valida aquí y no en las propiedades para que la app pueda mostrar un
    mensaje claro en vez de reventar con ZeroDivisionError en pantalla — que es
    lo que hacía la versión anterior cuando el precio de la especia era 0.
    """
    if natural_concentration <= 0:
        raise CalculationError(
            "La concentración del marcador en la especia natural debe ser mayor a 0."
        )
    if oleoresin_concentration <= 0:
        raise CalculationError(
            "La concentración del marcador en la oleorresina debe ser mayor a 0."
        )
    if not 0 < efficiency <= 1.0:
        raise CalculationError("La eficiencia de reemplazo debe estar entre 0 y 1.")
    if oleoresin_price <= 0:
        raise CalculationError("El precio de la oleorresina debe ser mayor a 0.")
    if natural_price < 0:
        raise CalculationError("El precio de la especia natural no puede ser negativo.")

    return Replacement(
        marker=marker,
        natural_concentration=natural_concentration,
        oleoresin_concentration=oleoresin_concentration,
        efficiency=efficiency,
        oleoresin_price=oleoresin_price,
        natural_price=natural_price,
        currency=currency,
    )


def sensitivity_curve(
    replacement: Replacement,
    *,
    low: float = 0.6,
    high: Optional[float] = None,
    steps: int = 40,
):
    """Ahorro % en función del precio de la oleorresina.

    Responde en vivo a "¿y si te pido 10 % de descuento?". Devuelve
    ``[(precio, ahorro_pct), …]``.

    El extremo superior se estira para que el precio de indiferencia entre en
    el gráfico cuando está a un múltiplo razonable del precio actual. Sin eso,
    en familias de altísimo factor de reemplazo (páprika en CU, con ratios de
    300×) la curva sale plana cerca del 100 % y no dice nada.
    """
    if replacement.natural_price <= 0:
        return []
    base = replacement.oleoresin_price

    if high is None:
        indifference_ratio = replacement.indifference_price / base if base else 1.5
        high = max(1.5, min(indifference_ratio * 1.12, 4.0))

    out = []
    for i in range(steps + 1):
        price = base * (low + (high - low) * i / steps)
        cost = price / replacement.effective_ratio
        out.append((price, (replacement.natural_price - cost) / replacement.natural_price * 100.0))
    return out
