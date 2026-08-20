#!/usr/bin/env python3
"""Genera el índice local del catálogo a partir de los dos Excel internos.

Este script se corre **localmente**. Los Excel y el índice resultante nunca
entran al repositorio ni salen del perímetro de Robertet: ``data/`` está en
``.gitignore``.

    python tools/build_index.py \\
        --first-choice "/ruta/Product Reference  Internal.xlsx" \\
        --askrc "/ruta/ASKRC 1 1.xlsx"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_layer.catalog import DEFAULT_INDEX, build  # noqa: E402
from data_layer.schema import MARKER_LABELS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-choice", required=True, help="Product Reference Internal.xlsx")
    parser.add_argument("--askrc", required=True, help="ASKRC 1 1.xlsx")
    parser.add_argument("--out", default=str(DEFAULT_INDEX), help="destino del índice")
    args = parser.parse_args()

    for label, path in (("First Choice", args.first_choice), ("ASKRC", args.askrc)):
        if not Path(path).exists():
            print(f"error: no encuentro el archivo de {label}: {path}", file=sys.stderr)
            return 1

    print("Leyendo catálogos…")
    catalog = build(args.first_choice, args.askrc)
    stats = catalog.stats()

    print("\nCatálogo unificado")
    print(f"  productos totales      {stats['total']:>6,}")
    print(f"    First Choice         {stats['first_choice']:>6,}")
    print(f"    Extended (ASKRC)     {stats['extended']:>6,}")
    print(f"  anulados (tachados)    {stats['void']:>6,}   <- excluidos de toda recomendación")
    print(f"  reemplazados           {stats['converted']:>6,}   <- se responde con el código vigente")
    print(f"  ofertables             {stats['offerable']:>6,}")
    print(f"  con marcador numérico  {stats['with_marker']:>6,}")

    counts: dict[str, int] = {}
    for product in catalog.offerable:
        for analyte in product.analytes:
            counts[analyte] = counts.get(analyte, 0) + 1
    if counts:
        print("\nCobertura de marcadores (sobre ofertables)")
        for analyte, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {MARKER_LABELS.get(analyte, analyte):<18} {n:>6,}")

    sin_marcador = [p for p in catalog.offerable if not p.has_marker]
    if sin_marcador:
        print(f"\n{len(sin_marcador):,} productos ofertables sin marcador numérico.")
        print("No son matcheables por especificación hasta que se capturen sus CoA.")

    if catalog.competitors:
        with_offer = sum(1 for c in catalog.competitors if c.has_offer)
        print(
            f"\nEquivalencias de competidor: {len(catalog.competitors)} "
            f"({with_offer} con producto Robertet)"
        )

    out = catalog.save(args.out)
    print(f"\nÍndice escrito en {out}")
    print("Recuerda: data/ no se versiona ni se despliega.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
