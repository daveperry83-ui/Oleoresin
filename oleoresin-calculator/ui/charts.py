"""Gráficos de la app.

Tres formas, cada una con un trabajo distinto:

* **Barras** — magnitud comparable: cuánto cuesta un kg de especia equivalente
  por cada vía.
* **Cascada** — composición: de dónde sale el ahorro anual, paso a paso.
* **Línea** — cambio sobre un eje continuo: cómo se mueve el ahorro cuando se
  mueve el precio, con el punto de indiferencia marcado.

Una sola escala por gráfico, marcas delgadas, ejes recesivos y etiquetas
directas en vez de un número sobre cada punto.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import plotly.graph_objects as go

from core.replacement import Replacement
from core.savings import BatchResult
from ui import theme


def _money(value: float, symbol: str) -> str:
    return f"{symbol} {value:,.2f}"


def cost_comparison(replacement: Replacement, symbol: str) -> go.Figure:
    """Costo por kg de especia equivalente: natural vs. oleorresina."""
    labels = ["Especia natural", "Oleorresina<br><span style='font-size:11px'>(costo en uso)</span>"]
    values = [replacement.natural_price, replacement.cost_in_use]
    colors = [theme.INK_NEUTRAL, theme.SERIES[1] if replacement.is_favourable else theme.BAD]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker=dict(color=colors, line=dict(color=theme.SURFACE_CARD, width=2)),
            width=0.5,
            text=[f"{v:,.2f}" for v in values],
            textposition="outside",
            textfont=dict(size=14, color=theme.TEXT_PRIMARY, family=theme.FONT),
            hovertemplate="%{x}<br>%{y:,.2f} " + symbol + "/kg<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        **theme.plotly_layout(
            height=300,
            yaxis=dict(
                gridcolor=theme.GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                title=dict(text=f"{symbol}/kg equivalente", font=dict(size=11)),
                range=[0, max(values) * 1.22 or 1],
            ),
            margin=dict(l=8, r=8, t=34, b=8),
        )
    )

    # Anotación de la brecha entre ambas barras.
    gap = replacement.saving_per_kg
    if abs(gap) > 1e-9:
        fig.add_annotation(
            x=0.5, xref="paper",
            y=(values[0] + values[1]) / 2,
            text=f"<b>{'−' if gap > 0 else '+'}{abs(gap):,.2f}</b><br>{symbol}/kg",
            showarrow=False,
            font=dict(size=12, color=theme.GOOD if gap > 0 else theme.BAD, family=theme.FONT),
            bgcolor="rgba(255,255,255,.85)",
        )
    return fig


def savings_waterfall(result: BatchResult, symbol: str) -> go.Figure:
    """Composición del ahorro anual, paso a paso.

    Se construye con barras flotantes en vez de ``go.Waterfall`` porque este
    último pinta la barra base y el total con el mismo color: la referencia
    (costo de la especia) saldría del color del resultado, que es justo lo que
    el lector no debe confundir. Aquí el color lo fija el papel de cada paso:
    referencia neutra, incrementos en la serie primaria, decrementos en rojo y
    el total en el verde de resultado — o rojo si el resultado es negativo.
    """
    steps = result.waterfall()

    labels: List[str] = []
    bases: List[float] = []
    heights: List[float] = []
    colors: List[str] = []
    texts: List[str] = []
    tops: List[float] = []

    running = 0.0
    for label, value, kind in steps:
        if kind == "base":
            bottom, top = 0.0, value
            running = value
            color = theme.INK_NEUTRAL
            text = f"{value:,.0f}"
        elif kind == "total":
            bottom, top = (0.0, running) if running >= 0 else (running, 0.0)
            value = running
            color = theme.SERIES[1] if running >= 0 else theme.BAD
            text = f"<b>{running:,.0f}</b>"
        else:
            if value >= 0:
                bottom, top = running, running + value
                color = theme.SERIES[0]
                text = f"+{value:,.0f}"
            else:
                bottom, top = running + value, running
                color = theme.BAD
                text = f"−{abs(value):,.0f}"
            running += value

        labels.append(label.replace(" ", "<br>", 1))
        bases.append(bottom)
        heights.append(max(abs(top - bottom), 1e-9))
        colors.append(color)
        texts.append(text)
        tops.append(max(top, bottom))

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=heights,
            base=bases,
            marker=dict(color=colors, line=dict(color=theme.SURFACE_CARD, width=2)),
            width=0.58,
            text=texts,
            textposition="outside",
            textfont=dict(size=11, color=theme.TEXT_PRIMARY, family=theme.FONT),
            customdata=[[s[1] if s[2] != "total" else result.net_saving] for s in steps],
            hovertemplate="%{x}<br>%{customdata[0]:,.0f} " + symbol + "<extra></extra>",
            cliponaxis=False,
        )
    )

    # Conectores entre pasos consecutivos.
    running = 0.0
    for index, (_, value, kind) in enumerate(steps[:-1]):
        running = value if kind == "base" else running + value
        fig.add_shape(
            type="line", xref="x", yref="y",
            x0=index + 0.29, x1=index + 0.71, y0=running, y1=running,
            line=dict(color="#B9C4D2", width=1.5, dash="dot"),
        )

    fig.add_hline(y=0, line=dict(color=theme.AXIS, width=1))

    span = max(tops + [abs(min(bases + [0]))]) or 1
    fig.update_layout(
        **theme.plotly_layout(
            height=330,
            bargap=0.34,
            yaxis=dict(gridcolor=theme.GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                       title=dict(text=symbol, font=dict(size=11)),
                       range=[min(bases + [0]) * 1.18 - span * 0.05, span * 1.16]),
            xaxis=dict(showgrid=False, zeroline=False, linecolor=theme.AXIS,
                       tickfont=dict(size=10)),
            margin=dict(l=8, r=8, t=34, b=8),
        )
    )
    return fig


def price_sensitivity(
    curve: Sequence[Tuple[float, float]],
    replacement: Replacement,
    symbol: str,
) -> Optional[go.Figure]:
    """Ahorro % en función del precio de la oleorresina."""
    if not curve:
        return None

    xs = [p for p, _ in curve]
    ys = [s for _, s in curve]

    fig = go.Figure()

    # Zona en la que la oleorresina deja de ser la opción económica.
    indifference = replacement.indifference_price
    if xs[0] <= indifference <= xs[-1]:
        fig.add_vrect(
            x0=indifference, x1=xs[-1],
            fillcolor=theme.BAD, opacity=0.07, line_width=0, layer="below",
        )

    fig.add_hline(y=0, line=dict(color="#C3CCD8", width=1.5))
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color=theme.SERIES[0], width=2.5, shape="spline"),
            hovertemplate="Precio %{x:,.2f} " + symbol + "/kg<br>Ahorro %{y:.1f} %<extra></extra>",
            name="Ahorro",
        )
    )

    saving = replacement.saving_pct
    if saving is not None:
        fig.add_trace(
            go.Scatter(
                x=[replacement.oleoresin_price], y=[saving], mode="markers+text",
                marker=dict(size=11, color=theme.SERIES[0],
                            line=dict(color=theme.SURFACE_CARD, width=2)),
                text=[f"  Hoy · {saving:.1f} %"], textposition="top right",
                textfont=dict(size=11, color=theme.TEXT_PRIMARY, family=theme.FONT),
                hovertemplate="Precio actual<extra></extra>",
                showlegend=False,
            )
        )

    if indifference > xs[-1]:
        # Familias de factor altísimo (páprika en CU) dejan el punto de
        # indiferencia muy fuera de escala; decirlo vale más que estirar el eje.
        fig.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.06, xanchor="right",
            text=f"Precio de indiferencia {indifference:,.0f} {symbol}/kg — fuera de escala",
            showarrow=False,
            font=dict(size=11, color=theme.TEXT_MUTED, family=theme.FONT),
        )
    elif xs[0] <= indifference <= xs[-1]:
        fig.add_trace(
            go.Scatter(
                x=[indifference], y=[0], mode="markers+text",
                marker=dict(size=11, color=theme.BAD,
                            line=dict(color=theme.SURFACE_CARD, width=2)),
                text=[f"Indiferencia · {indifference:,.0f}  "], textposition="top left",
                textfont=dict(size=11, color=theme.TEXT_PRIMARY, family=theme.FONT),
                hovertemplate="Precio de indiferencia<extra></extra>",
                showlegend=False,
            )
        )

    fig.update_layout(
        **theme.plotly_layout(
            height=330,
            hovermode="x unified",
            xaxis=dict(showgrid=False, zeroline=False, linecolor=theme.AXIS,
                       title=dict(text=f"Precio de la oleorresina ({symbol}/kg)",
                                  font=dict(size=11))),
            yaxis=dict(gridcolor=theme.GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                       ticksuffix=" %",
                       title=dict(text="Ahorro", font=dict(size=11))),
            margin=dict(l=8, r=8, t=34, b=8),
        )
    )
    return fig


def spec_coverage(candidates: List, symbol: str = "") -> Optional[go.Figure]:
    """Score de los candidatos recomendados, barras horizontales."""
    if not candidates:
        return None

    candidates = list(reversed(candidates))
    labels = [f"{c.product.code}" for c in candidates]
    scores = [c.score for c in candidates]
    colors = [
        theme.SERIES[1] if c.confidence == "high"
        else theme.WARN if c.confidence == "medium"
        else theme.BAD
        for c in candidates
    ]

    fig = go.Figure(
        go.Bar(
            y=labels, x=scores, orientation="h",
            marker=dict(color=colors, line=dict(color=theme.SURFACE_CARD, width=2)),
            width=0.55,
            text=[f"{s:.2f}" for s in scores],
            textposition="outside",
            textfont=dict(size=12, color=theme.TEXT_PRIMARY, family=theme.FONT),
            hovertemplate="%{y}<br>score %{x:.2f}<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        **theme.plotly_layout(
            height=max(150, 46 * len(candidates) + 60),
            xaxis=dict(range=[0, 1.12], showgrid=True, gridcolor=theme.GRID,
                       zeroline=False, linecolor="rgba(0,0,0,0)"),
            yaxis=dict(showgrid=False, zeroline=False, linecolor="rgba(0,0,0,0)",
                       tickfont=dict(size=12, family="ui-monospace, monospace")),
            margin=dict(l=8, r=30, t=20, b=8),
        )
    )
    return fig
