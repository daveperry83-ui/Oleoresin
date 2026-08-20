# Value Selling Calculator — Robertet

App Streamlit para vender oleorresinas contra especia natural. Dos pestañas que
comparten estado:

| Pestaña | Qué hace |
|---|---|
| 💰 **Calculadora de ahorro** | Factor de reemplazo, costo en uso, **precio de indiferencia**, ahorro anual con costos ocultos, y one-pager para el cliente |
| 🔍 **Recomendador** | Subes la spec del cliente → mejores productos vigentes del catálogo, con reporte de brecha parámetro por parámetro. Incluye buscador de reemplazo por código Kalsec / Mane |

Elegir un producto en el recomendador lo precarga en la calculadora con su
concentración real de marcador.

---

## ⚠️ El catálogo no viaja

`Product Reference Internal.xlsx` y `ASKRC.xlsx` son material interno de
Robertet. **Nunca entran a este repositorio ni salen del perímetro de la
empresa.**

- `.gitignore` excluye `data/`, `*.xlsx` y `*.parquet` desde el primer commit.
- El índice se genera **localmente** con `tools/build_index.py` y se queda en el
  disco de quien lo generó.
- No desplegar en Streamlit Community Cloud con el índice: es infraestructura
  pública de terceros. Para uso compartido, servidor interno de Robertet.
- Para correr en un equipo sin índice existe el **modo portátil**: la app ofrece
  subir los dos Excel y los mantiene solo en memoria de sesión, sin escribir a
  disco.

---

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone <url-del-repo>
cd oleoresin-calculator

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Generar el índice del catálogo

Una sola vez, y cada vez que cambien los Excel:

```bash
python tools/build_index.py \
    --first-choice "/ruta/a/Product Reference  Internal.xlsx" \
    --askrc        "/ruta/a/ASKRC 1 1.xlsx"
```

Imprime un resumen de lo que encontró:

```
Catálogo unificado
  productos totales       6,777
    First Choice             97
    Extended (ASKRC)      6,680
  anulados (tachados)       710   <- excluidos de toda recomendación
  reemplazados              915   <- se responde con el código vigente
  ofertables              5,152
  con marcador numérico   2,931
```

## Correr la app

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`.

## Precios de referencia (opcional)

Para consultar precios de especia seca en vivo hace falta una clave gratuita de
data.gov.in:

1. Regístrate en <https://www.data.gov.in/> → *My Account* → *API Key*.
2. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`
3. Pon la clave en `DATA_GOV_IN_API_KEY`.

Sin clave, la app cae al scraper del Spices Board de India y, si tampoco
responde, a entrada manual. **Ninguna fuente caída rompe la app.**

El tipo de cambio (Frankfurter, referencia BCE) no necesita clave.

> El precio mayorista de India **no es tu costo de compra en LATAM**: le falta
> grado de exportación, flete, arancel y margen de trader. La app lo etiqueta
> como referencia de mercado, con fuente y fecha visibles.

---

## Estructura

```
app.py                      Orquestación y UI (dos pestañas)
core/
  units.py                  Parseo de specs y normalización de unidades
  replacement.py            Factor, costo en uso, precio de indiferencia
  savings.py                Lote, costos ocultos, notas comerciales
data_layer/
  schema.py                 Modelo Product unificado
  ingest_first_choice.py    Product Reference + mapa Kalsec/Mane
  ingest_askrc.py           ASKRC (lee estilos de celda)
  catalog.py                Merge con prioridad First Choice, persistencia
  natural_spices.py         Marcadores de especia natural con fuente y rango
matching/
  normalize.py              Sinónimos bilingües y botánicos
  spec_parser.py            Spec del cliente → requisitos estructurados
  scorer.py                 Scoring, reporte de brecha, búsqueda por código
pricing/
  provider.py               Interfaz y cascada de degradación
  fx.py                     Tipo de cambio real (Frankfurter)
  market.py                 data.gov.in + Spices Board
  cache.py                  Caché en disco de datos públicos
ui/
  theme.py                  Paleta Robertet validada
  charts.py                 Comparativa, cascada, sensibilidad
  i18n.json / i18n.py       Localización ES/EN
export/one_pager.py         HTML de una página, imprimible a PDF
tools/build_index.py        Genera data/catalog.parquet (correr local)
tests/                      pytest
```

---

## Decisiones de diseño que conviene conocer

### El formato de celda es dato

La hoja `Legend` del ASKRC documenta que **el tachado significa "Void / Do Not
Sample"**. Son 710 productos, el 10 % del archivo. `pandas.read_excel()` y
`openpyxl` con `values_only=True` descartan esa información en silencio, así que
un parser convencional recomendaría producto descontinuado con total confianza y
sin ninguna señal de alarma.

`ingest_askrc.py` lee `cell.font.strike` explícitamente. El test
`test_ningun_anulado_es_ofertable` existe para que esto no se rompa nunca.

### El encabezado se mueve

La fila con `Code` varía entre la 3 y la 10 según la hoja del ASKRC. Se detecta,
no se asume. Y los encabezados nombran la misma columna de doce maneras
(`VO Max`, `MAX-VO`, `%VO Max`, `Max - Volatile Oil Content`…), así que el
analito se deduce por patrón en vez de por lista de variantes.

### Las unidades no son homogéneas

El ASKRC guarda piperina como fracción (`0.4` = 40 %); Product Reference como
porcentaje (`37 - 40`). Dentro del propio ASKRC, la columna de color trae
`41000` numérico y `100,000 - 102,000 CU` como texto. `tests/test_units.py`
cubre cada formato real encontrado, porque un error de unidad se propaga
silenciosamente hasta un precio.

### El navy de marca no sirve como color de gráfico

`#002857` se extrajo del logo. Validado contra superficie clara falla dos
verificaciones: luminosidad L 0.28 (fuera de la banda 0.43–0.77) y croma 0.095
(lee como gris). En una barra se ve casi negro y no se distingue de otras
series. Es color de **tinta**: barra superior, sidebar, títulos.

Los colores de datos son un paso más claro y saturado del mismo tono, validados
para daltonismo y contraste en claro y oscuro (CVD ΔE 9.7, visión normal ΔE
17.7, contraste ≥ 3:1). Ver `ui/theme.py`.

### El factor de eficiencia

`ratio = c_oleo / c_nat` es estequiometría pura del marcador. Exacto cuando el
atributo que el cliente compra *es* el marcador (color en CU, pungencia en SHU).
Para aceite volátil no: la extracción pierde top notes y aporta resinas no
volátiles. El factor de uso real queda por debajo del teórico.

Por eso hay un factor de eficiencia visible y editable (default 0.85 para
aromáticos, 1.00 para color y pungencia). Baja el ahorro reportado — de 33 % a
21 % en el caso de pimienta negra — pero es el número que se sostiene cuando el
cliente hace la prueba de planta.

### La app dice cuándo NO vender oleorresina

Para especias de alto contenido de volátiles (clavo, anís estrella, cardamomo)
el factor de reemplazo es bajo y el arbitraje rara vez favorece a la oleorresina
por precio puro. `commercial_advice()` lo señala y sugiere mover el argumento a
estandarización y microbiología. Una herramienta que solo dice "sí, ahorras" no
es creíble.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

119 tests. Los que más importan:

- `test_units.py` — cada formato de spec encontrado en los archivos reales
- `test_catalog_integrity.py::test_ningun_anulado_es_ofertable`
- `test_catalog_integrity.py::test_el_recomendador_nunca_propone_un_anulado`
- `test_replacement.py::test_precio_natural_cero_no_revienta`

---

## Pendientes conocidos

- **2,221 productos ofertables sin marcador numérico.** No son matcheables por
  especificación hasta que se capturen sus CoA. Prioridad: los capsicums
  (jalapeño, chipotle), que son alto volumen y se compran por SHU.
- **9 códigos de First Choice no están en el ASKRC** y siguen sin marcador:
  `23300100`, `NR0561`, `23300332`, `NR2116`, `NR2645`, `NR2849`, `NR2852`,
  `23300051`, `23300288`.
- **`NR0531` está duplicado** con dos specs distintas. El código no es clave
  única; hay que decidir cuál es el vigente.
- **Discrepancia de Scoville en capsicum.** Product Reference anota `~ 1M`;
  el ASKRC calcula 737,647–815,294 SHU sobre el mismo rango de capsaicina. Hace
  falta una sola fuente de verdad antes de publicar el número al cliente.
- El scraper del IPC (`ipcnet.org`) no está implementado: la página se renderiza
  por JavaScript y requiere Playwright o localizar el XHR interno.

---

Documento interno Robertet.
