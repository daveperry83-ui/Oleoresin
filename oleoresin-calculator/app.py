"""Value Selling Calculator — Robertet.

Una sola app con dos pestañas que comparten estado:

* **Calculadora de ahorro** — factor de reemplazo, costo en uso, precio de
  indiferencia y ahorro por lote sobre el catálogo real.
* **Recomendador** — sube la spec del cliente, la analiza y propone los
  productos vigentes que la cubren, con reporte de brecha.

Elegir un producto en el recomendador lo precarga en la calculadora con su
concentración de marcador tal como está en el catálogo.

    streamlit run app.py
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st

from core import replacement as rep
from core.replacement import CalculationError
from core.savings import HiddenCosts, batch, commercial_advice
from core.units import SOLUBILITY_LABELS
from data_layer import natural_spices
from data_layer.catalog import DEFAULT_INDEX, Catalog
from data_layer.schema import (
    DEFAULT_EFFICIENCY,
    MARKER_LABELS,
    SOURCE_FIRST_CHOICE,
    SOURCE_LABELS,
    Product,
    pick_marker,
)
from export import one_pager
from matching import spec_parser
from matching.scorer import (
    CONFIDENCE_LABELS,
    lookup_code,
    lookup_competitor,
    recommend,
)
from pricing import fx as fx_module
from pricing import market
from ui import charts, theme
from ui.i18n import LANGUAGES, ONE_PAGER_LANGUAGES, Translator

APP_ROOT = Path(__file__).parent
LOGO_PATH = APP_ROOT / "assets" / "robertet_logo_white.png"

st.set_page_config(
    page_title="Value Selling Calculator · Robertet",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(theme.CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Recursos cacheados
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _logo_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()


@st.cache_resource(show_spinner=False)
def _load_catalog_from_disk(path: str) -> Catalog:
    return Catalog.load(path)


@st.cache_data(ttl=43200, show_spinner=False)
def _fx_table(base: str):
    return fx_module.fetch(base)


@st.cache_data(ttl=86400, show_spinner=False)
def _market_quote(family: str, api_key: Optional[str], usda_key: Optional[str], usd_inr: float):
    class _Fx:
        rates = {"INR": usd_inr}

    return market.reference_price(family, api_key=api_key, usda_key=usda_key, fx=_Fx())


def _api_keys() -> tuple[Optional[str], Optional[str]]:
    """Obtiene claves de API de data.gov.in y USDA."""
    try:
        data_gov_key = st.secrets.get("DATA_GOV_IN_API_KEY") or None
    except Exception:
        data_gov_key = None

    try:
        usda_key = st.secrets.get("USDA_QUICKSTATS_API_KEY") or None
    except Exception:
        usda_key = None

    return data_gov_key, usda_key


# ---------------------------------------------------------------------------
# Fragmentos de UI
# ---------------------------------------------------------------------------

def topbar(t: Translator, fx_table) -> None:
    logo = _logo_uri()
    img = f'<img src="{logo}" alt="Robertet"/>' if logo else ""
    st.markdown(
        f"""
        <div class="rb-topbar">
          {img}
          <div class="rb-rule"></div>
          <div>
            <h1>{t('app_title')}</h1>
            <div class="rb-sub">{t('app_subtitle')} · v2.0</div>
          </div>
          <div class="rb-spacer"></div>
          <span class="rb-pill">{fx_table.provenance()}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, detail: str = "", tone: str = "") -> str:
    return (
        f'<div class="rb-kpi {tone}"><div class="k">{label}</div>'
        f'<div class="v">{value}</div><div class="d">{detail}</div></div>'
    )


def badge(text: str, tone: str = "info") -> str:
    return f'<span class="rb-badge {tone}">{text}</span>'


def source_badge(product: Product) -> str:
    tone = "info" if product.source == SOURCE_FIRST_CHOICE else "ext"
    return badge(SOURCE_LABELS.get(product.source, product.source), tone)


def product_caption(product: Product) -> str:
    bits = [SOLUBILITY_LABELS.get(product.solubility, "—")]
    for name, rng in list(product.analytes.items())[:3]:
        bits.append(f"{MARKER_LABELS.get(name, name)} {rng.format()}")
    return " · ".join(bits)


# ---------------------------------------------------------------------------
# Carga del catálogo (con modo portátil)
# ---------------------------------------------------------------------------

def resolve_catalog(t: Translator) -> Optional[Catalog]:
    """El catálogo nunca viaja: se lee del índice local o se carga por sesión."""
    if "session_catalog" in st.session_state:
        return st.session_state["session_catalog"]

    if Path(DEFAULT_INDEX).exists():
        try:
            with st.spinner(t("catalog_loading")):
                return _load_catalog_from_disk(str(DEFAULT_INDEX))
        except Exception as exc:  # pragma: no cover
            st.error(f"{t('catalog_missing')} {exc}")

    # En Streamlit Cloud: intenta descargar desde Google Drive
    if "STREAMLIT" in __import__("sys").modules or True:  # Detecta si es Streamlit
        try:
            from tools.load_from_drive import ensure_catalog_exists
            if ensure_catalog_exists():
                st.success(t("catalog_downloaded"))
                with st.spinner(t("catalog_loading")):
                    return _load_catalog_from_disk(str(DEFAULT_INDEX))
        except Exception as exc:
            pass  # Cae a la opción manual si falla

    st.warning(f"**{t('catalog_missing')}** {t('catalog_build')}")
    with st.expander(t("catalog_upload"), expanded=True):
        st.caption(t("catalog_session_note"))
        col_a, col_b = st.columns(2)
        first = col_a.file_uploader("Product Reference Internal.xlsx", type=["xlsx"], key="up_fc")
        askrc = col_b.file_uploader("ASKRC.xlsx", type=["xlsx"], key="up_ex")
        if first and askrc:
            import io

            from data_layer.catalog import build

            with st.spinner(t("catalog_processing")):
                catalog = build(io.BytesIO(first.getvalue()), io.BytesIO(askrc.getvalue()))
            st.session_state["session_catalog"] = catalog
            st.rerun()
    return None


# ---------------------------------------------------------------------------
# Pestaña 1 — Calculadora
# ---------------------------------------------------------------------------

def tab_calculator(t: Translator, catalog: Catalog, currency: str, fx_table, presentation: bool):
    products = [p for p in catalog.offerable if p.has_marker]
    if not products:
        st.error(t("catalog_no_products"))
        return

    families = sorted({p.family for p in products if p.family})
    symbol = fx_module.symbol(currency)

    left, right = st.columns([1, 2.4], gap="large")

    # ---------------------------------------------------------- entradas
    with left:
        preselected = st.session_state.pop("preselect_code", None)
        # Arrancar en pimienta negra: es el caso de uso más frecuente y el que
        # mejor ilustra la herramienta, no la primera familia del alfabeto.
        default_family = next(
            (i for i, f in enumerate(families) if f.startswith("pepper, black")), 0
        )
        if preselected:
            chosen = catalog.by_code(preselected)
            if chosen and chosen.family in families:
                default_family = families.index(chosen.family)

        st.markdown(f"##### 1 · {t('sec_product')}")
        family = st.selectbox(t("pick_family"), families, index=default_family,
                              format_func=str.title, key="calc_family")

        options = [p for p in products if p.family == family]
        options.sort(key=lambda p: (p.source != SOURCE_FIRST_CHOICE, p.description))
        index = 0
        if preselected:
            for i, p in enumerate(options):
                if p.code == preselected:
                    index = i
                    break

        product = st.selectbox(
            t("pick_product"), options, index=index,
            format_func=lambda p: f"{p.code} · {p.description[:44]}",
            key="calc_product",
        )
        st.markdown(f"{source_badge(product)} {badge(product_caption(product), 'info')}",
                    unsafe_allow_html=True)

        st.markdown(f"##### 2 · {t('sec_marker')}")
        markers = list(product.analytes)
        marker = st.selectbox(
            t("marker_label"), markers,
            index=markers.index(pick_marker(product.analytes)) if markers else 0,
            format_func=lambda m: MARKER_LABELS.get(m, m),
            key="calc_marker",
        )
        offered = product.analytes[marker]
        unit = offered.unit or "%"

        reference = natural_spices.for_marker(family, marker)
        default_natural = reference.typical if reference else 1.0
        step = 100.0 if unit in ("CU", "SHU") else 0.1

        c_nat = st.number_input(
            f"{t('conc_natural')} ({unit})",
            min_value=0.0, value=float(default_natural), step=step, format="%.4g",
            key="calc_cnat",
        )
        if reference:
            st.caption(f"{t('typical_range')}: {reference.range_text()} · {reference.source}")
        else:
            st.caption(t("catalog_no_reference"))

        c_oleo = st.number_input(
            f"{t('conc_oleoresin')} ({unit})",
            min_value=0.0, value=float(offered.midpoint), step=step, format="%.4g",
            key="calc_coleo",
        )
        st.caption(f"{t('catalog_price_label')}: **{offered.format()}** · {product.code}")

        efficiency = st.slider(
            t("efficiency"), min_value=0.50, max_value=1.00,
            value=float(DEFAULT_EFFICIENCY.get(marker, 0.90)), step=0.01,
            key="calc_eff", help=t("efficiency_help"),
        )

        st.markdown(f"##### 3 · {t('sec_prices')}")
        p_oleo = st.number_input(f"{t('price_oleoresin')} ({symbol}/kg)",
                                 min_value=0.0, value=80.0, step=1.0, key="calc_poleo")
        p_nat = st.number_input(f"{t('price_natural')} ({symbol}/kg)",
                                min_value=0.0, value=15.0, step=1.0, key="calc_pnat")

        if st.button(t("fetch_reference"), use_container_width=True):
            usd_inr = fx_table.rates.get("INR", 87.5)
            api_key, usda_key = _api_keys()
            quote = _market_quote(family, api_key, usda_key, usd_inr)
            st.session_state["market_quote"] = quote
            if quote is None:
                st.info(t("market_no_connection"))

        quote = st.session_state.get("market_quote")
        if quote is not None:
            converted = fx_table.convert(quote.value, currency) if currency != "USD" else quote.value
            st.markdown(
                f'<div class="rb-note"><b>{symbol} {converted:,.2f}/kg</b><br>'
                f'{quote.provenance()}<br><span style="font-size:11.5px">'
                f'{t("warn_market_price")}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown(f"##### 4 · {t('sec_volume')}")
        volume = st.number_input(t("volume_natural"), min_value=0.0, value=5000.0,
                                 step=100.0, key="calc_vol")

        with st.expander(t("sec_hidden")):
            hidden = HiddenCosts(
                logistics_per_kg=st.number_input(f"{t('hidden_logistics')} ({symbol})",
                                                 min_value=0.0, value=0.0, step=0.10),
                waste_pct_natural=st.number_input(t("hidden_waste"), min_value=0.0,
                                                  max_value=25.0, value=0.0, step=0.5),
                sterilization_per_kg=st.number_input(f"{t('hidden_sterilization')} ({symbol})",
                                                     min_value=0.0, value=0.0, step=0.10),
                changeover_cost=st.number_input(f"{t('hidden_changeover')} ({symbol})",
                                                min_value=0.0, value=0.0, step=100.0),
            )

    # ---------------------------------------------------------- resultados
    with right:
        try:
            calc = rep.build(
                marker=marker,
                natural_concentration=c_nat,
                oleoresin_concentration=c_oleo,
                oleoresin_price=p_oleo,
                natural_price=p_nat,
                efficiency=efficiency,
                currency=currency,
            )
        except CalculationError as exc:
            st.warning(str(exc))
            return

        family_label = (natural_spices.get(family).label(t.language)
                        if natural_spices.get(family) else family.title())

        st.markdown(
            f"""
            <div class="rb-hero">
              <div class="rb-ratio">1<small> : </small>{calc.effective_ratio:.1f}</div>
              <div class="rb-vr"></div>
              <div>
                <div class="rb-k">{t('hero_ratio')}</div>
                <div class="rb-v">{t('hero_caption', code=product.code,
                                     ratio=calc.effective_ratio, family=family_label)}</div>
                <div class="rb-n">{SOLUBILITY_LABELS.get(product.solubility, '—')} ·
                    {MARKER_LABELS.get(marker, marker)} {offered.format()} ·
                    {t('hero_detail', theoretical=calc.theoretical_ratio, efficiency=efficiency)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        result = batch(calc, volume, hidden)
        saving_pct = calc.saving_pct or 0.0
        favourable = calc.is_favourable

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi(t("kpi_ciu"), f"{symbol} {calc.cost_in_use:,.2f}", t("kpi_ciu_sub")),
                    unsafe_allow_html=True)
        k2.markdown(
            kpi(
                t("kpi_saving") if favourable else t("kpi_extra"),
                f"{symbol} {abs(calc.saving_per_kg):,.2f}",
                f"{'▲' if favourable else '▼'} {abs(saving_pct):.1f} %",
                "good" if favourable else "bad",
            ),
            unsafe_allow_html=True,
        )
        k3.markdown(
            kpi(t("kpi_indifference"), f"{symbol} {calc.indifference_price:,.2f}",
                t("kpi_indifference_sub"), "star"),
            unsafe_allow_html=True,
        )
        net = result.net_saving
        k4.markdown(
            kpi(
                t("kpi_annual") if net >= 0 else t("kpi_annual_cost"),
                f"{symbol} {abs(net):,.0f}",
                f"{result.oleoresin_kg:,.0f} kg de oleorresina · "
                f"{result.volume_reduction_pct or 0:.0f} % {t('batch_volume_cut')}",
                "good" if net >= 0 else "bad",
            ),
            unsafe_allow_html=True,
        )

        st.write("")
        c_left, c_right = st.columns([1, 1.5], gap="large")
        with c_left:
            st.markdown(f"**{t('chart_comparison')}**")
            st.plotly_chart(charts.cost_comparison(calc, symbol, t), use_container_width=True,
                            config={"displayModeBar": False})
        with c_right:
            st.markdown(f"**{t('chart_waterfall')}**")
            st.plotly_chart(charts.savings_waterfall(result, symbol), use_container_width=True,
                            config={"displayModeBar": False})

        st.markdown(f"**{t('chart_sensitivity')}**")
        st.caption(t("chart_sensitivity_sub"))
        curve = rep.sensitivity_curve(calc)
        figure = charts.price_sensitivity(curve, calc, symbol, t)
        if figure is not None:
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})

        if not presentation:
            notes = commercial_advice(calc)
            if notes:
                st.markdown(f"**{t('advice_title')}**")
                for note in notes:
                    st.markdown(f'<div class="rb-note">{note}</div>', unsafe_allow_html=True)

            st.divider()
            exp_left, exp_mid, exp_right = st.columns([1.6, 1, 1])
            customer = exp_left.text_input(t("customer_name"), key="calc_customer")
            onepager_lang = exp_mid.selectbox(
                t("onepager_language"), list(ONE_PAGER_LANGUAGES),
                format_func=lambda c: ONE_PAGER_LANGUAGES[c], key="onepager_lang",
            )
            html_doc = one_pager.build_html(
                product=product,
                replacement=calc,
                result=result,
                symbol=symbol,
                natural_label=family_label,
                marker=marker,
                gaps=st.session_state.get("last_gaps"),
                customer=customer,
                fx_note=fx_table.provenance(),
                language=onepager_lang,
            )
            exp_right.download_button(
                t("download_onepager"),
                data=html_doc.encode("utf-8"),
                file_name=f"value_selling_{product.code}.html",
                mime="text/html",
                use_container_width=True,
                help=t("onepager_help"),
            )


# ---------------------------------------------------------------------------
# Pestaña 2 — Recomendador
# ---------------------------------------------------------------------------

def _verdict_badge(verdict: str) -> str:
    icon = {"ok": "✓", "warn": "⚠", "fail": "✕"}[verdict]
    return badge(icon, verdict)


def render_gap_report(t: Translator, candidate) -> None:
    import pandas as pd

    rows = [
        {
            t("col_parameter"): g.parameter,
            t("col_requested"): g.requested,
            t("col_offered"): g.offered,
            t("col_verdict"): {"ok": t("verdict_ok"), "warn": t("verdict_warn"), "fail": t("verdict_fail")}[g.verdict],
            t("col_comment"): g.comment,
        }
        for g in candidate.gaps
    ]
    if not rows:
        st.caption(t("spec_no_params"))
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    tone = "fail" if candidate.blocking else ("warn" if candidate.deviations else "ok")
    st.markdown(
        f'<div class="rb-src">{candidate.deviations} {t("deviations_label")} · '
        f'{badge(candidate.suggested_action(), tone)}</div>',
        unsafe_allow_html=True,
    )


def tab_recommender(t: Translator, catalog: Catalog):
    st.markdown(f"##### {t('rec_upload')}")
    upload_col, paste_col = st.columns([1, 1.4], gap="large")

    with upload_col:
        uploaded = st.file_uploader(t("rec_upload"), type=["pdf", "xlsx", "xls", "csv", "txt"],
                                    help=t("rec_upload_help"), label_visibility="collapsed")
    with paste_col:
        pasted = st.text_area(t("rec_paste"), height=132, label_visibility="collapsed",
                              placeholder=t("rec_paste"))

    text = ""
    if uploaded is not None:
        text = spec_parser.read_upload(uploaded.name, uploaded.getvalue())
    if pasted.strip():
        text = f"{text}\n{pasted}" if text else pasted

    if not text.strip():
        st.info(t("rec_upload_help"))
        _competitor_panel(t, catalog)
        return

    spec = spec_parser.parse(text)
    st.markdown(f"**{t('rec_parsed')}**")
    st.markdown(f'<div class="rb-note">{spec.summary()}</div>', unsafe_allow_html=True)

    if spec.competitor_code:
        st.caption(f"{t('competitor_detected')}: {spec.competitor_code}")

    if spec.is_empty:
        st.warning(t("rec_none"))
        _competitor_panel(t, catalog)
        return

    candidates = recommend(spec, catalog, limit=5)
    if not candidates:
        st.warning(t("rec_no_match"))
        _competitor_panel(t, catalog)
        return

    st.markdown(f"##### {t('rec_results')}")
    stats = catalog.stats()
    st.caption(t("catalog_stats", **stats))

    figure = charts.spec_coverage(candidates)
    table_col, chart_col = st.columns([2.2, 1], gap="large")

    with table_col:
        import pandas as pd

        rows = []
        for c in candidates:
            p = c.product
            rows.append(
                {
                    t("col_code"): p.code,
                    t("col_description"): p.description[:38],
                    t("col_source"): SOURCE_LABELS.get(p.source, p.source),
                    t("col_solubility"): SOLUBILITY_LABELS.get(p.solubility, "—"),
                    t("col_score"): round(c.score, 2),
                    t("col_confidence"): CONFIDENCE_LABELS[c.confidence],
                    t("col_action"): c.suggested_action(),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(t("warn_confidence"))

    with chart_col:
        if figure is not None:
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})

    st.markdown(f"##### {t('rec_gap')}")
    labels = [f"{c.product.code} · {c.product.description[:30]}" for c in candidates]
    chosen = st.radio("Candidato", options=range(len(candidates)),
                      format_func=lambda i: labels[i], horizontal=True,
                      label_visibility="collapsed")
    candidate = candidates[chosen]

    head_left, head_right = st.columns([3, 1])
    with head_left:
        st.markdown(
            f'<span class="rb-code">{candidate.product.code}</span> '
            f'{source_badge(candidate.product)} '
            f'{badge(CONFIDENCE_LABELS[candidate.confidence], "ok" if candidate.confidence == "high" else "warn")}'
            f'<div class="rb-src">{candidate.product.description} · '
            f'{product_caption(candidate.product)}</div>',
            unsafe_allow_html=True,
        )
    with head_right:
        if candidate.product.has_marker and st.button(t("rec_use"), use_container_width=True,
                                                      type="primary"):
            st.session_state["preselect_code"] = candidate.product.code
            st.session_state["goto_calculator"] = True
            st.rerun()

    st.session_state["last_gaps"] = candidate.gaps
    render_gap_report(t, candidate)
    _competitor_panel(t, catalog)


def _competitor_panel(t: Translator, catalog: Catalog):
    st.divider()
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(f"##### {t('comp_title')}")
        query = st.text_input(t("comp_search"), placeholder="3.01 · 02.040.06 · oleoresin paprika")
        if query:
            matches = lookup_competitor(query, catalog)
            if not matches:
                st.caption(t("comp_none"))
            for entry, product in matches[:6]:
                if product is not None:
                    verdict = badge(entry.verdict[:38] or "—", "ok" if entry.confidence == "high" else "warn")
                    target = f'<span class="rb-code">{product.code}</span> {product.description[:34]}'
                elif entry.robertet_code:
                    verdict = badge(entry.verdict[:38], "warn")
                    target = f'<span class="rb-code">{entry.robertet_code}</span> (no está en el índice)'
                else:
                    verdict = badge(t("comp_no_offer"), "fail")
                    target = "—"
                st.markdown(
                    f'<div style="margin-bottom:9px">'
                    f'<span class="rb-code">{entry.competitor} {entry.competitor_code}</span> '
                    f'{entry.competitor_desc[:34]} → {target}<br>{verdict}</div>',
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown(f"##### {t('code_search')}")
        code = st.text_input("Código", placeholder="NR3101", label_visibility="collapsed")
        if code:
            result = lookup_code(code, catalog)
            if not result.found:
                st.caption(result.message)
            else:
                product = result.product
                st.markdown(
                    f'<span class="rb-code">{product.code}</span> {source_badge(product)}<br>'
                    f'<div class="rb-src">{product.description} · {product_caption(product)}</div>',
                    unsafe_allow_html=True,
                )
                if result.message:
                    st.error(result.message)
                if result.replacement is not None:
                    st.success(f"{t('equivalent_active')}: {result.replacement.code} · "
                               f"{result.replacement.description}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    with st.sidebar:
        language = st.radio("🌍 Idioma / Language", list(LANGUAGES),
                            format_func=lambda c: LANGUAGES[c], horizontal=True)
        t = Translator(language)
        currency = st.selectbox(t("currency"), list(fx_module.CURRENCIES),
                                format_func=lambda c: f"{c} · {fx_module.CURRENCIES[c][1]}")
        presentation = st.toggle(t("presentation_mode"), value=False)

    fx_table = _fx_table("USD")
    if currency != "USD":
        st.session_state["fx_note"] = fx_table.provenance()

    topbar(t, fx_table)

    catalog = resolve_catalog(t)
    if catalog is None:
        st.stop()

    with st.sidebar:
        stats = catalog.stats()
        st.divider()
        st.caption(t("catalog_stats", **stats))
        if fx_table.stale:
            st.warning(t("fx_no_connection"))

    # Navegación por radio en vez de st.tabs: st.tabs no se puede cambiar por
    # código, y el botón "Usar en la calculadora" del recomendador necesita
    # llevar al usuario a la otra pestaña. El CSS le da aspecto de pestañas.
    pages = [f"💰 {t('tab_calculator')}", f"🔍 {t('tab_recommender')}"]
    if st.session_state.pop("goto_calculator", False):
        st.session_state["nav"] = pages[0]
    st.session_state.setdefault("nav", pages[0])

    page = st.radio("Sección", pages, key="nav", horizontal=True,
                    label_visibility="collapsed")

    if page == pages[0]:
        tab_calculator(t, catalog, currency, fx_table, presentation)
    else:
        tab_recommender(t, catalog)

    st.markdown(
        f'<div class="rb-src" style="text-align:center;margin-top:22px">{t("footer")}</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
