"""Descarga catálogos desde Google Drive y construye el índice.

Usado por Streamlit Cloud cuando data/catalog.parquet no existe.
Los archivos se descargan como .xlsx directamente desde Drive.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

# IDs de los sheets en Google Drive
ASKRC_ID = "1zfTL6lAESMTteza0i_EArxCcHmmbzCuS"
PRODUCT_REF_ID = "1ySJUWpmxiSz19sB9yATeNavFYGykN9LY"


def download_sheet_as_excel(sheet_id: str) -> bytes:
    """Descarga un Google Sheet como archivo Excel."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    except Exception as e:
        raise RuntimeError(f"No se pudo descargar sheet {sheet_id}: {e}")


def ensure_catalog_exists(data_dir: Path = Path("data")) -> bool:
    """Descarga y construye el catálogo si no existe."""
    catalog_path = data_dir / "catalog.parquet"
    
    if catalog_path.exists():
        return True
    
    print("⏳ Descargando catálogos desde Google Drive...")
    
    # Crea directorio data/
    data_dir.mkdir(exist_ok=True)
    
    # Descarga los archivos
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        print("  • ASKRC...")
        askrc_data = download_sheet_as_excel(ASKRC_ID)
        askrc_path = tmpdir / "ASKRC.xlsx"
        askrc_path.write_bytes(askrc_data)
        
        print("  • Product Reference...")
        prod_ref_data = download_sheet_as_excel(PRODUCT_REF_ID)
        prod_ref_path = tmpdir / "Product Reference Internal.xlsx"
        prod_ref_path.write_bytes(prod_ref_data)
        
        # Construye el índice
        print("  • Procesando...")
        from data_layer.ingest_askrc import load as load_askrc
        from data_layer.ingest_first_choice import load as load_first_choice
        from data_layer.catalog import Catalog
        
        askrc = load_askrc(str(askrc_path))
        prod_ref = load_first_choice(str(prod_ref_path))
        
        catalog = Catalog.merge(askrc, prod_ref)
        catalog.save(str(catalog_path))
        
        print(f"✓ Catálogo guardado en {catalog_path}")
    
    return True


if __name__ == "__main__":
    ensure_catalog_exists()
