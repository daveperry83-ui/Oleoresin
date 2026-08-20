"""Identidad visual Robertet.

El navy de marca ``#002857`` se extrajo del logo corporativo. **No se usa como
color de gráfico**: con L 0.28 y croma 0.095 queda fuera de la banda de
luminosidad y por debajo del piso de croma, así que en una barra se lee casi
negro y no se distingue de otras series. Es color de tinta.

Los colores de datos son un paso más claro y saturado del mismo tono. La paleta
completa está validada para daltonismo y contraste en modo claro y oscuro
(separación CVD ΔE 9.7, visión normal ΔE 17.7, contraste ≥ 3:1 en ambos modos).
"""
from __future__ import annotations

# --- marca -----------------------------------------------------------------
NAVY = "#002857"          # color corporativo, tal cual el logo
NAVY_800 = "#001F45"
NAVY_600 = "#0A3D75"
NAVY_100 = "#E7EDF5"
NAVY_050 = "#F2F6FA"

# --- superficies y texto ---------------------------------------------------
SURFACE = "#FAFAF8"
SURFACE_CARD = "#FFFFFF"
BORDER = "#D9E0EA"
TEXT_PRIMARY = "#0F1B2E"
TEXT_SECONDARY = "#4A5B72"
TEXT_MUTED = "#7A8AA0"
INK_NEUTRAL = "#8497AE"   # serie de referencia (la especia natural)

# --- series de datos (validadas) -------------------------------------------
SERIES = ("#215FA6", "#0E8E74", "#B07C1F", "#8659C4")
SERIES_DARK = ("#4585CE", "#1FA283", "#BC8A30", "#9A70D8")

GOOD = "#0E8E74"
WARN = "#B07C1F"
BAD = "#A8443A"

STATUS_COLORS = {"ok": GOOD, "warn": WARN, "fail": BAD}

GRID = "#EDF0F4"
AXIS = "#C9D2DE"

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def plotly_layout(**overrides) -> dict:
    """Layout base para todos los gráficos: ejes recesivos, sin ruido."""
    layout = dict(
        font=dict(family=FONT, size=12, color=TEXT_SECONDARY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=28, b=8),
        hoverlabel=dict(
            bgcolor=SURFACE_CARD,
            bordercolor=BORDER,
            font=dict(family=FONT, size=12, color=TEXT_PRIMARY),
        ),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=AXIS, ticks="outside",
                   tickcolor=AXIS, ticklen=4),
        yaxis=dict(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)"),
        showlegend=False,
    )
    layout.update(overrides)
    return layout


CSS = f"""
<style>
  .stApp {{ background: {SURFACE}; }}
  html, body, [class*="css"] {{ font-family: {FONT}; }}

  /* ------------------------------------------------ barra de marca */
  .rb-topbar {{
    background: {NAVY}; color: #fff; border-radius: 10px;
    padding: 15px 22px; display: flex; align-items: center; gap: 18px;
    margin-bottom: 6px;
  }}
  .rb-topbar img {{ height: 40px; }}
  .rb-topbar .rb-rule {{ width: 1px; height: 32px; background: rgba(255,255,255,.28); }}
  .rb-topbar h1 {{
    font-size: 15px !important; margin: 0 !important; font-weight: 500;
    letter-spacing: .06em; text-transform: uppercase; color: #fff;
  }}
  .rb-topbar .rb-sub {{ font-size: 12px; color: rgba(255,255,255,.66); margin-top: 2px; }}
  .rb-topbar .rb-spacer {{ flex: 1; }}
  .rb-pill {{
    font-size: 11px; padding: 4px 11px; border-radius: 99px;
    border: 1px solid rgba(255,255,255,.3); color: rgba(255,255,255,.85);
    white-space: nowrap;
  }}

  /* ------------------------------------------------ hero */
  .rb-hero {{
    background: linear-gradient(135deg, {NAVY} 0%, {NAVY_600} 100%);
    color: #fff; border-radius: 10px; padding: 22px 28px;
    display: flex; align-items: center; gap: 28px; flex-wrap: wrap;
  }}
  .rb-hero .rb-ratio {{
    font-size: 56px; font-weight: 600; line-height: 1; letter-spacing: -.03em;
    font-variant-numeric: tabular-nums;
  }}
  .rb-hero .rb-ratio small {{ font-size: 20px; font-weight: 400; opacity: .72; }}
  .rb-hero .rb-k {{ font-size: 10.5px; letter-spacing: .11em; text-transform: uppercase; opacity: .72; }}
  .rb-hero .rb-v {{ font-size: 18px; font-weight: 500; margin-top: 4px; }}
  .rb-hero .rb-n {{ font-size: 12.5px; opacity: .78; margin-top: 4px; }}
  .rb-hero .rb-vr {{ width: 1px; align-self: stretch; background: rgba(255,255,255,.22); }}

  /* ------------------------------------------------ tarjetas KPI */
  .rb-kpi {{
    background: {SURFACE_CARD}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 14px 16px; height: 100%;
  }}
  .rb-kpi .k {{ font-size: 10.5px; letter-spacing: .07em; text-transform: uppercase; color: {TEXT_MUTED}; }}
  .rb-kpi .v {{
    font-size: 25px; font-weight: 600; margin-top: 6px; letter-spacing: -.02em;
    color: {TEXT_PRIMARY}; font-variant-numeric: tabular-nums;
  }}
  .rb-kpi .d {{ font-size: 11.5px; margin-top: 3px; color: {TEXT_SECONDARY}; }}
  .rb-kpi.good {{ border-color: #BFDCD2; background: #F3FAF7; }}
  .rb-kpi.good .v {{ color: {GOOD}; }}
  .rb-kpi.bad {{ border-color: #E9C9C4; background: #FDF5F4; }}
  .rb-kpi.bad .v {{ color: {BAD}; }}
  .rb-kpi.star {{ border-color: {NAVY}; box-shadow: 0 0 0 1px {NAVY}; }}
  .rb-kpi.star .v {{ color: {NAVY}; }}

  /* ------------------------------------------------ badges */
  .rb-badge {{
    display: inline-block; font-size: 11px; font-weight: 500;
    padding: 2px 9px; border-radius: 5px; margin-right: 5px;
  }}
  .rb-badge.ok   {{ background: #E9F6F1; color: #0B6B57; }}
  .rb-badge.warn {{ background: #FBF3E3; color: #8A5F13; }}
  .rb-badge.fail {{ background: #FAECEA; color: #8C382F; }}
  .rb-badge.info {{ background: {NAVY_050}; color: {NAVY}; }}
  .rb-badge.ext  {{ background: #F4F1FA; color: #5A3B93; }}

  .rb-code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
    background: {NAVY_050}; border: 1px solid {BORDER}; padding: 1px 6px;
    border-radius: 4px; color: {NAVY};
  }}
  .rb-src {{
    font-size: 11px; color: {TEXT_MUTED}; margin-top: 8px;
    padding-top: 8px; border-top: 1px dashed {BORDER};
  }}
  .rb-note {{
    background: {NAVY_050}; border-left: 3px solid {NAVY_600};
    padding: 10px 14px; border-radius: 0 7px 7px 0; font-size: 13px;
    color: {TEXT_SECONDARY}; margin: 6px 0;
  }}

  section[data-testid="stSidebar"] {{ background: {NAVY_050}; }}
  section[data-testid="stSidebar"] h2 {{ font-size: 13px !important; color: {NAVY_600}; }}

  /* La navegación principal es un st.radio (st.tabs no se puede cambiar por
     código y el botón "Usar en la calculadora" necesita hacerlo), presentado
     como barra de pestañas. Se ancla en .st-key-nav, la clase que Streamlit
     pone en el contenedor a partir del key del widget. */
  .st-key-nav div[role="radiogroup"] {{
    gap: 2px; border-bottom: 1px solid {BORDER}; margin-bottom: 16px;
  }}
  .st-key-nav label[data-testid="stRadioOption"] {{
    padding: 9px 20px 10px; margin: 0; border-radius: 8px 8px 0 0;
    border-bottom: 2px solid transparent; cursor: pointer;
    transition: background .12s, border-color .12s;
  }}
  .st-key-nav label[data-testid="stRadioOption"] > div > div > div:first-child {{
    display: none;   /* el círculo del radio */
  }}
  .st-key-nav label[data-testid="stRadioOption"] p {{
    font-size: 14px; font-weight: 500; color: {TEXT_SECONDARY}; margin: 0;
  }}
  .st-key-nav label[data-testid="stRadioOption"]:hover {{ background: {NAVY_050}; }}
  .st-key-nav label[data-selected="true"] {{ border-bottom-color: {NAVY}; }}
  .st-key-nav label[data-selected="true"] p {{ color: {NAVY}; font-weight: 600; }}
  div[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
</style>
"""
