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
        "replaces": "1 kg de {code} reemplaza {ratio:.2f} kg de {family}",
        "theoretical_factor": "factor teórico {theoretical:.2f} × eficiencia {efficiency:.2f}",
        "cost_in_use": "Costo en uso",
        "per_kg_equivalent": "por kg equivalente",
        "saving": "Ahorro",
        "extra_cost": "Costo extra",
        "per_kg": "por kg",
        "vs_natural_spice": "vs. especia natural",
        "indifference_price": "Precio de indiferencia",
        "price_ceiling": "techo de precio",
        "net_saving": "Ahorro neto anual",
        "net_cost": "Costo neto anual",
        "over_kg": "sobre {kg:,.0f} kg",
        "annual_scenario": "Escenario anual",
        "natural_to_replace": "Especia natural a reemplazar",
        "oleoresin_needed": "Oleorresina necesaria",
        "volume_reduction": "Reducción de volumen a manejar",
        "cost_with_natural": "Costo con especia natural",
        "cost_with_oleoresin": "Costo con oleorresina",
        "assumptions": "Supuestos",
        "in_natural_spice": "en especia natural",
        "in_oleoresin": "en oleorresina",
        "replacement_efficiency": "Eficiencia de reemplazo",
        "oleoresin_price": "Precio oleorresina",
        "natural_price": "Precio especia natural",
        "footer": "Documento interno Robertet. Cifras basadas en los supuestos listados arriba; el "
                  "desempeño real debe confirmarse en prueba de planta. Las referencias de mercado "
                  "son indicativas y no constituyen costo de compra.",
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
        "replaces": "1 kg of {code} replaces {ratio:.2f} kg of {family}",
        "theoretical_factor": "theoretical factor {theoretical:.2f} × efficiency {efficiency:.2f}",
        "cost_in_use": "Cost in use",
        "per_kg_equivalent": "per equivalent kg",
        "saving": "Saving",
        "extra_cost": "Extra cost",
        "per_kg": "per kg",
        "vs_natural_spice": "vs. natural spice",
        "indifference_price": "Indifference price",
        "price_ceiling": "price ceiling",
        "net_saving": "Net annual saving",
        "net_cost": "Net annual cost",
        "over_kg": "over {kg:,.0f} kg",
        "annual_scenario": "Annual scenario",
        "natural_to_replace": "Natural spice to replace",
        "oleoresin_needed": "Oleoresin needed",
        "volume_reduction": "Volume reduction to handle",
        "cost_with_natural": "Cost with natural spice",
        "cost_with_oleoresin": "Cost with oleoresin",
        "assumptions": "Assumptions",
        "in_natural_spice": "in natural spice",
        "in_oleoresin": "in oleoresin",
        "replacement_efficiency": "Replacement efficiency",
        "oleoresin_price": "Oleoresin price",
        "natural_price": "Natural spice price",
        "footer": "Robertet internal document. Figures based on the assumptions listed above; "
                  "actual performance should be confirmed in a plant trial. Market references are "
                  "indicative and do not constitute purchase cost.",
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
        "replaces": "1 kg de {code} substitui {ratio:.2f} kg de {family}",
        "theoretical_factor": "fator teórico {theoretical:.2f} × eficiência {efficiency:.2f}",
        "cost_in_use": "Custo em uso",
        "per_kg_equivalent": "por kg equivalente",
        "saving": "Economia",
        "extra_cost": "Custo extra",
        "per_kg": "por kg",
        "vs_natural_spice": "vs. especiaria natural",
        "indifference_price": "Preço de indiferença",
        "price_ceiling": "teto de preço",
        "net_saving": "Economia líquida anual",
        "net_cost": "Custo líquido anual",
        "over_kg": "sobre {kg:,.0f} kg",
        "annual_scenario": "Cenário anual",
        "natural_to_replace": "Especiaria natural a substituir",
        "oleoresin_needed": "Oleoresina necessária",
        "volume_reduction": "Redução de volume a manusear",
        "cost_with_natural": "Custo com especiaria natural",
        "cost_with_oleoresin": "Custo com oleoresina",
        "assumptions": "Premissas",
        "in_natural_spice": "em especiaria natural",
        "in_oleoresin": "em oleoresina",
        "replacement_efficiency": "Eficiência de substituição",
        "oleoresin_price": "Preço da oleoresina",
        "natural_price": "Preço da especiaria natural",
        "footer": "Documento interno Robertet. Valores baseados nas premissas listadas acima; o "
                  "desempenho real deve ser confirmado em teste de planta. As referências de mercado "
                  "são indicativas e não constituem custo de compra.",
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
        "replaces": "1 kg de {code} remplace {ratio:.2f} kg de {family}",
        "theoretical_factor": "facteur théorique {theoretical:.2f} × efficacité {efficiency:.2f}",
        "cost_in_use": "Coût en usage",
        "per_kg_equivalent": "par kg équivalent",
        "saving": "Économie",
        "extra_cost": "Coût supplémentaire",
        "per_kg": "par kg",
        "vs_natural_spice": "vs. épice naturelle",
        "indifference_price": "Prix d'indifférence",
        "price_ceiling": "plafond de prix",
        "net_saving": "Économie nette annuelle",
        "net_cost": "Coût net annuel",
        "over_kg": "sur {kg:,.0f} kg",
        "annual_scenario": "Scénario annuel",
        "natural_to_replace": "Épice naturelle à remplacer",
        "oleoresin_needed": "Oléorésine nécessaire",
        "volume_reduction": "Réduction du volume à manipuler",
        "cost_with_natural": "Coût avec épice naturelle",
        "cost_with_oleoresin": "Coût avec oléorésine",
        "assumptions": "Hypothèses",
        "in_natural_spice": "dans l'épice naturelle",
        "in_oleoresin": "dans l'oléorésine",
        "replacement_efficiency": "Efficacité de remplacement",
        "oleoresin_price": "Prix de l'oléorésine",
        "natural_price": "Prix de l'épice naturelle",
        "footer": "Document interne Robertet. Chiffres basés sur les hypothèses listées ci-dessus ; la "
                  "performance réelle doit être confirmée par un essai en usine. Les références de "
                  "marché sont indicatives et ne constituent pas un coût d'achat.",
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
      <div class="d">{_esc(_get_text(language, 'replaces').format(code=product.code, ratio=replacement.effective_ratio, family=natural_label))}</div>
      <div class="n">{_esc(product.description)} ·
          {_esc(SOLUBILITY_LABELS.get(product.solubility, '—'))} ·
          {_esc(MARKER_LABELS.get(marker, marker))}
          {_esc(product.analyte_display(marker))} ·
          {_esc(_get_text(language, 'theoretical_factor').format(theoretical=replacement.theoretical_ratio, efficiency=replacement.efficiency))}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="k">{_get_text(language, 'cost_in_use')}</div>
      <div class="v">{symbol} {replacement.cost_in_use:,.2f}</div>
      <div class="d">{_get_text(language, 'per_kg_equivalent')}</div></div>
    <div class="kpi {'good' if favourable else 'bad'}">
      <div class="k">{_get_text(language, 'saving') if favourable else _get_text(language, 'extra_cost')} {_get_text(language, 'per_kg')}</div>
      <div class="v">{symbol} {abs(replacement.saving_per_kg):,.2f}</div>
      <div class="d">{abs(saving_pct):.1f} % {_get_text(language, 'vs_natural_spice')}</div></div>
    <div class="kpi star"><div class="k">{_get_text(language, 'indifference_price')}</div>
      <div class="v">{symbol} {replacement.indifference_price:,.2f}</div>
      <div class="d">{_get_text(language, 'price_ceiling')}</div></div>
    <div class="kpi {'good' if result.net_saving >= 0 else 'bad'}">
      <div class="k">{_get_text(language, 'net_saving') if result.net_saving >= 0 else _get_text(language, 'net_cost')}</div>
      <div class="v">{symbol} {abs(result.net_saving):,.0f}</div>
      <div class="d">{_esc(_get_text(language, 'over_kg').format(kg=result.natural_kg))}</div></div>
  </div>

  <div class="two">
    <div>
      <h2>{_get_text(language, 'annual_scenario')}</h2>
      <table>
        <tr><td>{_get_text(language, 'natural_to_replace')}</td>
            <td style="text-align:right">{result.natural_kg:,.0f} kg</td></tr>
        <tr><td>{_get_text(language, 'oleoresin_needed')}</td>
            <td style="text-align:right"><b>{result.oleoresin_kg:,.0f} kg</b></td></tr>
        <tr><td>{_get_text(language, 'volume_reduction')}</td>
            <td style="text-align:right">{result.volume_reduction_pct or 0:.0f} %</td></tr>
        <tr><td>{_get_text(language, 'cost_with_natural')}</td>
            <td style="text-align:right">{symbol} {result.natural_cost:,.0f}</td></tr>
        <tr><td>{_get_text(language, 'cost_with_oleoresin')}</td>
            <td style="text-align:right">{symbol} {result.oleoresin_cost:,.0f}</td></tr>
      </table>
    </div>
    <div>
      <h2>{_get_text(language, 'assumptions')}</h2>
      <table>
        <tr><td>{_esc(MARKER_LABELS.get(marker, marker))} {_get_text(language, 'in_natural_spice')}</td>
            <td style="text-align:right">{replacement.natural_concentration:,.4g}</td></tr>
        <tr><td>{_esc(MARKER_LABELS.get(marker, marker))} {_get_text(language, 'in_oleoresin')}</td>
            <td style="text-align:right">{replacement.oleoresin_concentration:,.4g}</td></tr>
        <tr><td>{_get_text(language, 'replacement_efficiency')}</td>
            <td style="text-align:right">{replacement.efficiency:.2f}</td></tr>
        <tr><td>{_get_text(language, 'oleoresin_price')}</td>
            <td style="text-align:right">{symbol} {replacement.oleoresin_price:,.2f}/kg</td></tr>
        <tr><td>{_get_text(language, 'natural_price')}</td>
            <td style="text-align:right">{symbol} {replacement.natural_price:,.2f}/kg</td></tr>
      </table>
    </div>
  </div>

  {gap_rows}

  <footer>
    {_get_text(language, 'footer')}{(' · ' + _esc(fx_note)) if fx_note else ''}
  </footer>
</body></html>"""
