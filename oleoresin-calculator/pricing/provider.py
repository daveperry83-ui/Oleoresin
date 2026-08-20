"""Capa de precios: tipo de cambio real y referencias de mercado.

Principio de diseño: **ninguna fuente caída puede romper la app**. Todo pasa por
una cascada de degradación que termina siempre en un valor utilizable, con la
procedencia visible para que el usuario sepa qué tan fresco es el dato.

    API → scraper → caché en disco → último valor conocido → entrada manual

Aviso importante que la UI debe mostrar: el precio mayorista de India **no es
el costo de compra en LATAM**. Le falta grado de exportación, flete, arancel y
margen de trader. Es señal de tendencia y ancla de negociación, no costo.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Quote:
    """Una cotización con su procedencia. La procedencia no es opcional."""

    value: float
    currency: str
    unit: str
    source: str
    date: Optional[_dt.date] = None
    url: str = ""
    grade: str = ""
    stale: bool = False
    note: str = ""

    @property
    def age_days(self) -> Optional[int]:
        if self.date is None:
            return None
        return (_dt.date.today() - self.date).days

    def provenance(self) -> str:
        bits = [self.source]
        if self.grade:
            bits.append(self.grade)
        if self.date:
            bits.append(self.date.strftime("%d-%b-%Y"))
        age = self.age_days
        if age is not None and age > 1:
            bits.append(f"hace {age} días")
        return " · ".join(bits)


class PriceProvider:
    """Interfaz común. Una implementación nunca lanza: devuelve ``None``."""

    name = "base"

    def fetch(self, commodity: str) -> Optional[Quote]:  # pragma: no cover
        raise NotImplementedError


class ProviderChain:
    """Prueba proveedores en orden y devuelve el primero que responda."""

    def __init__(self, *providers: PriceProvider) -> None:
        self.providers = providers

    def fetch(self, commodity: str) -> Optional[Quote]:
        for provider in self.providers:
            try:
                quote = provider.fetch(commodity)
            except Exception:
                # Una fuente caída degrada, no rompe.
                continue
            if quote is not None:
                return quote
        return None
