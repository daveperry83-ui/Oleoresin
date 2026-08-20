"""One-pager para dejarle al cliente.

Genera un HTML autocontenido de una página, con la marca Robertet, listo para
imprimir a PDF desde el navegador (Ctrl/Cmd + P → Guardar como PDF). Se eligió
HTML en vez de una librería de PDF para no arrastrar dependencias binarias:
la app tiene que poder correr en la laptop de un comercial sin instalar nada
fuera de pip.

Regla de confidencialidad: el one-pager es material que sale de Robertet, así
que **no** incluye la tabla completa de candidatos ni ningún dato de catálogo
más allá del producto recomendado.
"""
from __future__ import annotations

import base64
import datetime as _dt
import html
from pathlib import Path
from typing import List, Optional

from core.replacement import Replacement
from core.savings import BatchResult
from core.units import SOLUBILITY_LABELS
from data_layer.schema import MARKER_LABELS, Product
from ui import theme

LOGO = Path(__file__).resolve().parent.parent / "assets" / "robertet_logo_navy.png"


def _logo_uri() -> str:
    if not LOGO.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()


def _esc(value) -> str:
    return html.escape(str(value))


#: Traducciones de meses y textos para el one-pager
_TRANSLATIONS = {
    "es": {
        "months": ("enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"),
        "title": "Value Selling · Análisis de reemplazo",
        "subtitle": "Oleorresina vs. especia natural",
        "client": "Cliente",
        "spec_compliance": "Cumplimiento de especificación",
        "parameter": "Parámetro",
        "customer_requires": "Pide el cliente",
        "robertet_offers": "Ofrece Robertet",
    },
    "en": {
        "months": ("January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"),
        "title": "Value Selling · Replacement Analysis",
        "subtitle": "Oleoresin vs. natural spice",
        "client": "Customer",
        "spec_compliance": "Specification Compliance",
        "parameter": "Parameter",
        "customer_requires": "Customer Requires",
        "robertet_offers": "Robertet Offers",
    },
    "pt": {
        "months": ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
                   "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"),
        "title": "Value Selling · Análise de Substituição",
        "subtitle": "Oleoresina vs. especiaria natural",
        "client": "Cliente",
        "spec_compliance": "Conformidade de Especificação",
        "parameter": "Parâmetro",
        "customer_requires": "Cliente Requer",
        "robertet_offers": "Robertet Oferece",
    },
    "fr": {
        "months": ("janvier", "février", "mars", "avril", "mai", "juin",
                   "juillet", "août", "septembre", "octobre", "novembre", "décembre"),
        "title": "Value Selling · Analyse de Remplacement",
        "subtitle": "Oléorésine vs. épice naturelle",
        "client": "Client",
        "spec_compliance": "Conformité aux Spécifications",
        "parameter": "Paramètre",
        "customer_requires": "Le Client Exige",
        "robertet_offers": "Robertet Propose",
    },
}

def _get_text(language: str, key: str) -> str:
    """Obtiene el texto traducido o fallback al español."""
    if language not in _TRANSLATIONS:
        language = "es"
    return _TRANSLATIONS[language].get(key, _TRANSLATIONS["es"].get(key, key))

def _format_date(date: _dt.date, language: str = "es") -> str:
    months = _TRANSLATIONS.get(language, _TRANSLATIONS["es"])["months"]
    month_name = months[date.month - 1]
    return f"{date.day} de {month_name} de {date.year}" if language == "es" else f"{month_name} {date.day}, {date.year}"


def build_html(
    *,
    product: Product,
    replacement: Replacement,
    result: BatchResult,
    symbol: str,
    natural_label: str,
    marker: str,
    gaps: Optional[List] = None,
    customer: str = "",
    author: str = "",
    fx_note: str = "",
    language: str = "es",
) -> str:
    """Devuelve el HTML completo del one-pager."""
    today = _format_date(_dt.date.today(), language)
    favourable = replacement.is_favourable
    saving_pct = replacement.saving_pct or 0.0
    logo = _logo_uri()

    gap_rows = ""
    if gaps:
        icons = {"ok": "✓", "warn": "⚠", "fail": "✕"}
        gap_rows = "".join(
            f"<tr><td>{_esc(g.parameter)}</td><td>{_esc(g.requested)}</td>"
            f"<td>{_esc(g.offered)}</td>"
            f'<td class="v {g.verdict}">{icons[g.verdict]}</td></tr>'
            for g in gaps
        )
        gap_rows = f"""
        <h2>{_get_text(language, 'spec_compliance')}</h2>
        <table class="grid">
          <thead><tr><th>{_get_text(language, 'parameter')}</th><th>{_get_text(language, 'customer_requires')}</th>
                     <th>{_get_text(language, 'robertet_offers')}</th><th></th></tr></thead>
          <tbody>{gap_rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="{language}"><head><meta charset="utf-8"/>
<title>Value Selling · {_esc(product.code)}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: {theme.FONT}; color: {theme.TEXT_PRIMARY}; margin: 0;
          font-size: 12px; line-height: 1.5; }}
  header {{ display: flex; align-items: center; gap: 18px;
            border-bottom: 2px solid {theme.NAVY}; padding-bottom: 12px; }}
  header img {{ height: 46px; }}
  header .t {{ font-size: 15px; font-weight: 600; letter-spacing: .04em;
               text-transform: uppercase; color: {theme.NAVY}; }}
  header .s {{ font-size: 11px; color: {theme.TEXT_MUTED}; margin-top: 2px; }}
  header .spacer {{ flex: 1; }}
  header .meta {{ font-size: 10.5px; color: {theme.TEXT_MUTED}; text-align: right; }}
  h2 {{ font-size: 12px; letter-spacing: .07em; text-transform: uppercase;
        color: {theme.NAVY_600}; margin: 18px 0 8px; }}
  .hero {{ background: {theme.NAVY}; color: #fff; border-radius: 8px;
           padding: 16px 20px; display: flex; align-items: center; gap: 22px;
           margin-top: 14px; }}
  .hero .r {{ font-size: 40px; font-weight: 600; line-height: 1; }}
  .hero .r small {{ font-size: 16px; opacity: .7; font-weight: 400; }}
  .hero .d {{ font-size: 13px; font-weight: 500; }}
  .hero .n {{ font-size: 11px; opacity: .8; margin-top: 3px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; }}
  .kpi {{ border: 1px solid {theme.BORDER}; border-radius: 8px; padding: 10px 12px; }}
  .kpi .k {{ font-size: 9px; letter-spacing: .06em; text-transform: uppercase;
             color: {theme.TEXT_MUTED}; }}
  .kpi .v {{ font-size: 19px; font-weight: 600; margin-top: 4px; }}
  .kpi .d {{ font-size: 10px; color: {theme.TEXT_SECONDARY}; }}
  .kpi.good .v {{ color: {theme.GOOD}; }}
  .kpi.bad .v {{ color: {theme.BAD}; }}
  .kpi.star {{ border-color: {theme.NAVY}; }}
  .kpi.star .v {{ color: {theme.NAVY}; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; }}
  th {{ text-align: left; font-size: 9px; letter-spacing: .06em; text-transform: uppercase;
        color: {theme.TEXT_MUTED}; padding: 0 8px 5px; border-bottom: 1px solid {theme.BORDER}; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #EEF1F5; }}
  td.v {{ text-align: center; font-weight: 700; }}
  td.v.ok {{ color: {theme.GOOD}; }}
  td.v.warn {{ color: {theme.WARN}; }}
  td.v.fail {{ color: {theme.BAD}; }}
  .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
  footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid {theme.BORDER};
            font-size: 9.5px; color: {theme.TEXT_MUTED}; }}
  @media print {{ body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
</style></head>
<body>
  <header>
    {'<img src="' + logo + '" alt="Robertet"/>' if logo else ''}
    <div>
      <div class="t">{_get_text(language, 'title')}</div>
      <div class="s">{_get_text(language, 'subtitle')}</div>
    </div>
    <div class="spacer"></div>
    <div class="meta">
      {(_get_text(language, 'client') + ': ' + _esc(customer) + '<br>') if customer else ''}
      {today}{('<br>' + _esc(author)) if author else ''}
    </div>
  </header>

  <div class="hero">
    <div class="r">1<small> : </small>{replacement.effective_ratio:.1f}</div>
    <div>
      <div class="d">1 kg de {_esc(product.code)} reemplaza
          {replacement.effective_ratio:.2f} kg de {_esc(natural_label)}</div>
      <div class="n">{_esc(product.description)} ·
          {_esc(SOLUBILITY_LABELS.get(product.solubility, '—'))} ·
          {_esc(MARKER_LABELS.get(marker, marker))}
          {_esc(product.analyte_display(marker))} ·
          factor teórico {replacement.theoretical_ratio:.2f} ×
          eficiencia {replacement.efficiency:.2f}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="k">Costo en uso</div>
      <div class="v">{symbol} {replacement.cost_in_use:,.2f}</div>
      <div class="d">por kg equivalente</div></div>
    <div class="kpi {'good' if favourable else 'bad'}">
      <div class="k">{'Ahorro' if favourable else 'Costo extra'} por kg</div>
      <div class="v">{symbol} {abs(replacement.saving_per_kg):,.2f}</div>
      <div class="d">{abs(saving_pct):.1f} % vs. especia natural</div></div>
    <div class="kpi star"><div class="k">Precio de indiferencia</div>
      <div class="v">{symbol} {replacement.indifference_price:,.2f}</div>
      <div class="d">techo de precio</div></div>
    <div class="kpi {'good' if result.net_saving >= 0 else 'bad'}">
      <div class="k">{'Ahorro' if result.net_saving >= 0 else 'Costo'} neto anual</div>
      <div class="v">{symbol} {abs(result.net_saving):,.0f}</div>
      <div class="d">sobre {result.natural_kg:,.0f} kg</div></div>
  </div>

  <div class="two">
    <div>
      <h2>Escenario anual</h2>
      <table>
        <tr><td>Especia natural a reemplazar</td>
            <td style="text-align:right">{result.natural_kg:,.0f} kg</td></tr>
        <tr><td>Oleorresina necesaria</td>
            <td style="text-align:right"><b>{result.oleoresin_kg:,.0f} kg</b></td></tr>
        <tr><td>Reducción de volumen a manejar</td>
            <td style="text-align:right">{result.volume_reduction_pct or 0:.0f} %</td></tr>
        <tr><td>Costo con especia natural</td>
            <td style="text-align:right">{symbol} {result.natural_cost:,.0f}</td></tr>
        <tr><td>Costo con oleorresina</td>
            <td style="text-align:right">{symbol} {result.oleoresin_cost:,.0f}</td></tr>
      </table>
    </div>
    <div>
      <h2>Supuestos</h2>
      <table>
        <tr><td>{_esc(MARKER_LABELS.get(marker, marker))} en especia natural</td>
            <td style="text-align:right">{replacement.natural_concentration:,.4g}</td></tr>
        <tr><td>{_esc(MARKER_LABELS.get(marker, marker))} en oleorresina</td>
            <td style="text-align:right">{replacement.oleoresin_concentration:,.4g}</td></tr>
        <tr><td>Eficiencia de reemplazo</td>
            <td style="text-align:right">{replacement.efficiency:.2f}</td></tr>
        <tr><td>Precio oleorresina</td>
            <td style="text-align:right">{symbol} {replacement.oleoresin_price:,.2f}/kg</td></tr>
        <tr><td>Precio especia natural</td>
            <td style="text-align:right">{symbol} {replacement.natural_price:,.2f}/kg</td></tr>
      </table>
    </div>
  </div>

  {gap_rows}

  <footer>
    Documento interno Robertet. Cifras basadas en los supuestos listados arriba; el
    desempeño real debe confirmarse en prueba de planta. Las referencias de mercado
    son indicativas y no constituyen costo de compra.{(' · ' + _esc(fx_note)) if fx_note else ''}
  </footer>
</body></html>"""
