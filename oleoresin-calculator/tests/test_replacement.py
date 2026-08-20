"""Cálculo de reemplazo, ahorro y precio de indiferencia."""
import pytest

from core.replacement import CalculationError, build, sensitivity_curve
from core.savings import HiddenCosts, batch, commercial_advice


@pytest.fixture
def pimienta():
    """Caso de referencia: pimienta negra NR3101, 5 % vs 40 %, 80 y 15 USD/kg."""
    return build(
        marker="piperine",
        natural_concentration=5.0,
        oleoresin_concentration=40.0,
        oleoresin_price=80.0,
        natural_price=15.0,
        efficiency=0.85,
    )


class TestFactores:
    def test_factor_teorico(self, pimienta):
        assert pimienta.theoretical_ratio == pytest.approx(8.0)

    def test_factor_efectivo(self, pimienta):
        assert pimienta.effective_ratio == pytest.approx(6.8)

    def test_eficiencia_uno_no_cambia_nada(self):
        calc = build(marker="colour", natural_concentration=130.0,
                     oleoresin_concentration=40000.0, oleoresin_price=20.0,
                     natural_price=6.0, efficiency=1.0)
        assert calc.effective_ratio == calc.theoretical_ratio


class TestEconomia:
    def test_costo_en_uso(self, pimienta):
        assert pimienta.cost_in_use == pytest.approx(11.7647, rel=1e-4)

    def test_ahorro_por_kg(self, pimienta):
        assert pimienta.saving_per_kg == pytest.approx(3.2353, rel=1e-4)

    def test_ahorro_porcentaje(self, pimienta):
        assert pimienta.saving_pct == pytest.approx(21.57, rel=1e-3)

    def test_precio_de_indiferencia(self, pimienta):
        """El número que la versión anterior no calculaba."""
        assert pimienta.indifference_price == pytest.approx(102.0)

    def test_espacio_de_precio(self, pimienta):
        assert pimienta.price_headroom == pytest.approx(22.0)

    def test_en_indiferencia_el_ahorro_es_cero(self, pimienta):
        en_el_techo = build(
            marker="piperine", natural_concentration=5.0, oleoresin_concentration=40.0,
            oleoresin_price=pimienta.indifference_price, natural_price=15.0, efficiency=0.85,
        )
        assert en_el_techo.saving_per_kg == pytest.approx(0.0, abs=1e-9)

    def test_caso_desfavorable(self):
        calc = build(marker="volatile_oil", natural_concentration=8.0,
                     oleoresin_concentration=18.0, oleoresin_price=90.0,
                     natural_price=12.0, efficiency=0.85)
        assert not calc.is_favourable
        assert calc.saving_per_kg < 0


class TestValidaciones:
    """La versión anterior reventaba con ZeroDivisionError en pantalla."""

    def test_precio_natural_cero_no_revienta(self):
        calc = build(marker="piperine", natural_concentration=5.0,
                     oleoresin_concentration=40.0, oleoresin_price=80.0,
                     natural_price=0.0, efficiency=1.0)
        assert calc.saving_pct is None  # sin división por cero

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(natural_concentration=0.0),
            dict(oleoresin_concentration=0.0),
            dict(oleoresin_price=0.0),
            dict(natural_price=-1.0),
            dict(efficiency=0.0),
            dict(efficiency=1.5),
        ],
    )
    def test_entradas_invalidas(self, kwargs):
        base = dict(marker="piperine", natural_concentration=5.0,
                    oleoresin_concentration=40.0, oleoresin_price=80.0,
                    natural_price=15.0, efficiency=0.85)
        base.update(kwargs)
        with pytest.raises(CalculationError):
            build(**base)


class TestLote:
    def test_oleorresina_necesaria(self, pimienta):
        assert pimienta.oleoresin_needed(5000) == pytest.approx(735.29, rel=1e-4)

    def test_ahorro_directo_anual(self, pimienta):
        result = batch(pimienta, 5000)
        assert result.natural_cost == pytest.approx(75000.0)
        assert result.oleoresin_cost == pytest.approx(58823.5, rel=1e-4)
        assert result.direct_saving == pytest.approx(16176.5, rel=1e-4)

    def test_sin_costos_ocultos_el_neto_es_el_directo(self, pimienta):
        result = batch(pimienta, 5000)
        assert result.net_saving == pytest.approx(result.direct_saving)

    def test_costos_ocultos_suman_y_restan(self, pimienta):
        hidden = HiddenCosts(logistics_per_kg=0.75, waste_pct_natural=2.0,
                             sterilization_per_kg=0.30, changeover_cost=900.0)
        result = batch(pimienta, 5000)
        con_ocultos = batch(pimienta, 5000, hidden)
        assert con_ocultos.net_saving > result.net_saving
        assert con_ocultos.changeover_cost == 900.0

    def test_reduccion_de_volumen(self, pimienta):
        result = batch(pimienta, 5000)
        assert result.volume_reduction_pct == pytest.approx(85.29, rel=1e-3)

    def test_cascada_cierra_en_el_neto(self, pimienta):
        hidden = HiddenCosts(logistics_per_kg=0.75, changeover_cost=900.0)
        result = batch(pimienta, 5000, hidden)
        steps = result.waterfall()
        assert steps[0][2] == "base"
        assert steps[-1][2] == "total"
        acumulado = sum(v for _, v, kind in steps if kind != "total")
        assert acumulado == pytest.approx(result.net_saving)

    def test_volumen_negativo(self, pimienta):
        with pytest.raises(CalculationError):
            batch(pimienta, -10)


class TestSensibilidad:
    def test_cruza_cero_en_la_indiferencia(self, pimienta):
        curve = sensitivity_curve(pimienta, low=0.5, high=1.6, steps=200)
        cruce = min(curve, key=lambda point: abs(point[1]))
        assert cruce[0] == pytest.approx(pimienta.indifference_price, rel=0.02)

    def test_monotona_decreciente(self, pimienta):
        curve = sensitivity_curve(pimienta)
        savings = [s for _, s in curve]
        assert savings == sorted(savings, reverse=True)

    def test_sin_precio_natural_no_hay_curva(self):
        calc = build(marker="piperine", natural_concentration=5.0,
                     oleoresin_concentration=40.0, oleoresin_price=80.0,
                     natural_price=0.0, efficiency=1.0)
        assert sensitivity_curve(calc) == []


class TestNotasComerciales:
    def test_avisa_cuando_el_factor_es_bajo(self):
        """Clavo: 16 % natural vs 50 % en oleorresina da un factor de ~3."""
        calc = build(marker="volatile_oil", natural_concentration=16.0,
                     oleoresin_concentration=50.0, oleoresin_price=60.0,
                     natural_price=14.0, efficiency=0.85)
        notas = " ".join(commercial_advice(calc)).lower()
        assert "factor de reemplazo es bajo" in notas

    def test_avisa_cuando_no_conviene(self):
        calc = build(marker="volatile_oil", natural_concentration=8.0,
                     oleoresin_concentration=18.0, oleoresin_price=90.0,
                     natural_price=12.0, efficiency=0.85)
        notas = " ".join(commercial_advice(calc)).lower()
        assert "más cara" in notas

    def test_avisa_de_eficiencia_uno_en_aceite_volatil(self):
        calc = build(marker="volatile_oil", natural_concentration=2.0,
                     oleoresin_concentration=25.0, oleoresin_price=70.0,
                     natural_price=9.0, efficiency=1.0)
        notas = " ".join(commercial_advice(calc)).lower()
        assert "perfil sensorial" in notas
