"""Los errores de unidad son el fallo más costoso de esta herramienta.

Los dos catálogos expresan el mismo analito en escalas distintas y mezclan
números con texto. Cada formato real encontrado en los archivos tiene aquí su
caso.
"""
import math

import pytest

from core.units import (
    SpecRange,
    UnitError,
    capsaicin_to_shu,
    inr_kg_to_usd_kg,
    inr_quintal_to_usd_kg,
    normalize_solubility,
    normalize_yesno,
    parse_spec_value,
)


class TestParseSpecValue:
    @pytest.mark.parametrize(
        "raw, low, high, kind",
        [
            ("22 min", 22.0, None, "min"),
            ("28.5 min", 28.5, None, "min"),
            ("19 - 21", 19.0, 21.0, "range"),
            ("2 - 4", 2.0, 4.0, "range"),
            ("3 -7", 3.0, 7.0, "range"),
            ("11.5 - 14", 11.5, 14.0, "range"),
            ("9.25-10.25%", 9.25, 10.25, "range"),
        ],
    )
    def test_formatos_de_product_reference(self, raw, low, high, kind):
        result = parse_spec_value(raw, analyte="volatile_oil")
        assert (result.low, result.high, result.kind) == (low, high, kind)

    def test_separador_de_miles(self):
        result = parse_spec_value("40,000 - 41,000 CU", analyte="colour")
        assert (result.low, result.high, result.unit) == (40000.0, 41000.0, "CU")

    def test_max_con_unidad_intercalada(self):
        """'200 CU Max' es un máximo, no un valor puntual.

        La unidad se interpone entre el número y la palabra 'Max'; un regex
        ingenuo lo lee como punto y la app publicaría un color equivocado.
        """
        result = parse_spec_value("200 CU Max", analyte="colour")
        assert result.kind == "max"
        assert result.high == 200.0
        assert result.low is None

    def test_anotacion_de_scoville_no_contamina_el_valor(self):
        """'~ 1M' es una anotación comercial, no el valor medido."""
        result = parse_spec_value("6.27 - 6.93% HPLC ~ 1M", analyte="capsaicin")
        assert (result.low, result.high) == (6.27, 6.93)

    def test_parentesis_de_millones_se_ignora(self):
        result = parse_spec_value("13.2% MIN (2 MILLION CAP)", analyte="capsaicin")
        assert result.kind == "min"
        assert result.low == 13.2

    def test_texto_con_nombre_del_analito(self):
        result = parse_spec_value("8.5% curcumin", analyte="curcumin")
        assert result.midpoint == 8.5

    def test_fraccion_del_askrc_se_escala_a_porcentaje(self):
        """El ASKRC guarda piperina como 0.4; Product Reference como 37-40."""
        result = parse_spec_value(0.4, analyte="piperine", assume_fraction=True)
        assert result.midpoint == pytest.approx(40.0)

    def test_valor_ya_en_porcentaje_no_se_reescala(self):
        result = parse_spec_value(22.0, analyte="volatile_oil", assume_fraction=True)
        assert result.midpoint == pytest.approx(22.0)

    def test_colour_nunca_se_trata_como_fraccion(self):
        result = parse_spec_value(41000, analyte="colour", assume_fraction=True)
        assert result.midpoint == 41000.0

    @pytest.mark.parametrize("raw", [None, "", "  ", "<Not Entered>", "N/A", "—"])
    def test_vacios(self, raw):
        assert parse_spec_value(raw) is None

    def test_nan_devuelve_none(self):
        assert parse_spec_value(float("nan"), analyte="piperine") is None


class TestSatisfies:
    def test_rango_completo_dentro_de_lo_pedido(self):
        offered = SpecRange(37.0, 40.0, "range", "%")
        requested = SpecRange(35.0, None, "min", "%")
        assert offered.satisfies(requested) == 1.0

    def test_minimo_insuficiente_no_cumple(self):
        """'≥ 18 %' NO satisface '≥ 35 %' aunque ambos se solapen al infinito.

        Este era el falso positivo: medir por anchura de intervalo daba 1.0
        porque el intervalo pedido es infinito hacia arriba.
        """
        offered = SpecRange(18.0, None, "min", "%")
        requested = SpecRange(35.0, None, "min", "%")
        assert offered.satisfies(requested) < 1.0

    def test_sin_interseccion(self):
        offered = SpecRange(10.0, 12.0, "range", "%")
        requested = SpecRange(35.0, None, "min", "%")
        assert offered.satisfies(requested) == 0.0

    def test_solapamiento_parcial(self):
        offered = SpecRange(30.0, 40.0, "range", "%")
        requested = SpecRange(35.0, None, "min", "%")
        coverage = offered.satisfies(requested)
        assert 0.0 < coverage < 1.0

    def test_formato_legible(self):
        assert SpecRange(22.0, None, "min", "%").format() == "≥ 22 %"
        assert SpecRange(None, 200.0, "max", "CU").format() == "≤ 200 CU"
        assert SpecRange(40000.0, 41000.0, "range", "CU").format() == "40,000 – 41,000 CU"

    def test_extremos_invertidos_se_corrigen(self):
        assert SpecRange(40.0, 20.0, "range").low == 20.0

    def test_rango_sin_extremos_es_error(self):
        with pytest.raises(UnitError):
            SpecRange(None, None, "range")


class TestConversiones:
    def test_capsaicina_a_scoville(self):
        """6.93 % con el factor del ASKRC da ~815,294 SHU, no 1 M."""
        assert capsaicin_to_shu(6.93) == pytest.approx(815294.1, rel=1e-5)

    def test_capsaicina_negativa(self):
        with pytest.raises(UnitError):
            capsaicin_to_shu(-1)

    def test_mandi_quintal_a_usd_kg(self):
        """70,000 INR/quintal a 87.5 INR/USD = 8.00 USD/kg."""
        assert inr_quintal_to_usd_kg(70000, 87.5) == pytest.approx(8.0)

    def test_rupias_kg_a_usd_kg(self):
        """708 Rs/kg (pimienta Cochin) a 87.5 = 8.09 USD/kg."""
        assert inr_kg_to_usd_kg(708, 87.5) == pytest.approx(8.0914, rel=1e-4)

    def test_tipo_de_cambio_invalido(self):
        with pytest.raises(UnitError):
            inr_quintal_to_usd_kg(1000, 0)


class TestVocabularios:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("OIL SOLUBLE", "oil"),
            ("OIL", "oil"),
            ("WATER DISPERSIBLE", "water_dispersible"),
            ("Water/Oil Dispers-able", "water_dispersible"),
            ("WATER SOLUBLE", "water_soluble"),
            ("WATER", "water_soluble"),
            ("", "unknown"),
            (None, "unknown"),
        ],
    )
    def test_solubilidad_normalizada(self, raw, expected):
        """Los catálogos usan cinco etiquetas para tres conceptos."""
        assert normalize_solubility(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [("Y", True), ("YES", True), ("K", True), ("KP", True), ("H", True),
         ("N", False), ("NO", False), ("", None), ("<Not Entered>", None)],
    )
    def test_si_no(self, raw, expected):
        assert normalize_yesno(raw) is expected
