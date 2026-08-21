"""Bitácora de recomendaciones usadas, para exportar un histórico mensual.

Cada vez que un vendedor confirma "Usar en la calculadora" desde el
recomendador, queda una fila aquí: qué pidió el cliente, qué producto se
propuso y con qué confianza. Es el registro que responde "¿qué le
recomendamos a quién y cuándo?" sin depender de que alguien se acuerde de
anotarlo.

Nota de arquitectura — importante para quien despliegue esto en Streamlit
Community Cloud: el disco del contenedor **no es persistente entre
reinicios**. Este log vive mientras el contenedor siga arriba (normalmente
días o semanas de uso continuo), pero no sustituye un respaldo real. La app
ofrece descargar el Excel del mes bajo demanda — conviene bajarlo con
regularidad, o correr la app en un servidor interno con disco persistente
(ver sección 8 del roadmap: "el catálogo no viaja").
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

LOG_PATH = Path("data/recommendation_log.csv")

FIELDS = [
    "timestamp", "customer", "family", "product_code", "description",
    "confidence", "score", "solubility_requested", "language",
]


def append(entry: Dict) -> None:
    """Agrega una fila. `entry` puede traer solo algunas claves de FIELDS."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LOG_PATH.exists()
    row = {k: entry.get(k, "") for k in FIELDS}
    if not row.get("timestamp"):
        row["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def read_all():
    import pandas as pd

    if not LOG_PATH.exists():
        return pd.DataFrame(columns=FIELDS)
    return pd.read_csv(LOG_PATH)


def count_this_month() -> int:
    df = read_all()
    if df.empty:
        return 0
    import pandas as pd

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    now = datetime.now()
    return int(((ts.dt.year == now.year) & (ts.dt.month == now.month)).sum())


def month_export_xlsx(year: int, month: int) -> bytes:
    """Devuelve el Excel del mes indicado, en memoria (sin tocar disco)."""
    import io

    import pandas as pd

    df = read_all()
    if not df.empty:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df[(ts.dt.year == year) & (ts.dt.month == month)]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Recomendaciones")
    return buf.getvalue()
