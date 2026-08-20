"""Lectura de la especificación que manda el cliente."""
import pytest

from matching.normalize import detect_family, normalize
from matching.spec_parser import parse

SPEC_EN = """Black Pepper Oleoresin
Oil soluble
Piperine: 35% min
Volatile oil: 15% min
Kosher certified, non-GMO
Shelf life 18 months
"""

SPEC_ES = """Oleorresina de pimienta negra
Soluble en aceite
Piperina: 35 % mínimo
Aceite volátil: 15 % mínimo
Certificado kosher, sin transgénicos
"""


class TestParseoBasico:
    def test_familia_en_ingles(self):
        assert parse(SPEC_EN).family == "pepper, black and green"

    def test_familia_en_espanol(self):
        assert parse(SPEC_ES).family == "pepper, black and green"

    def test_solubilidad(self):
        assert parse(SPEC_EN).solubility == "oil"
        assert parse(SPEC_ES).solubility == "oil"

    def test_cada_analito_toma_su_propio_valor(self):
        """La alternancia del regex se tragaba el resto de la expresión y
        'Volatile oil: 15% min' capturaba el 35 % de la línea anterior."""
        spec = parse(SPEC_EN)
        assert spec.analytes["piperine"].low == 35.0
        assert spec.analytes["volatile_oil"].low == 15.0

    def test_analitos_en_espanol(self):
        spec = parse(SPEC_ES)
        assert spec.analytes["piperine"].low == 35.0
        assert spec.analytes["volatile_oil"].low == 15.0

    def test_requisitos(self):
        spec = parse(SPEC_EN)
        assert spec.requirements.get("kosher")
        assert spec.requirements.get("gmo_free")

    def test_vida_de_anaquel(self):
        assert parse(SPEC_EN).shelf_life_min == 18.0

    def test_spec_vacia(self):
        assert parse("").is_empty
        assert parse("   ").is_empty


class TestFormatosVariados:
    def test_color_con_separador_de_miles(self):
        spec = parse("Paprika oleoresin, colour value 40,000 - 60,000 CU, oil soluble")
        rango = spec.analytes["colour"]
        assert (rango.low, rango.high) == (40000.0, 60000.0)
        assert spec.family == "paprika"

    def test_scoville(self):
        spec = parse("Capsicum oleoresin 500,000 SHU min, water dispersible")
        assert spec.analytes["scoville"].low == 500000.0
        assert spec.solubility == "water_dispersible"

    def test_sin_soya(self):
        assert parse("Ginger oleoresin, soy-free").requirements.get("no_soy")
        assert parse("Oleorresina de jengibre, sin soya").requirements.get("no_soy")

    def test_organico(self):
        assert parse("Organic turmeric oleoresin, curcumin 8% min").requirements.get("organic")

    def test_codigo_de_competidor(self):
        assert parse("Replacement for Kalsec 3.01 black pepper").competitor_code == "3.01"

    def test_curcumina(self):
        spec = parse("Turmeric oleoresin, curcumin 8.5% min, water dispersible")
        assert spec.analytes["curcumin"].low == 8.5
        assert spec.family == "turmeric"

    def test_resumen_legible(self):
        resumen = parse(SPEC_EN).summary()
        assert "Piperina ≥ 35 %" in resumen
        assert "Aceite volátil ≥ 15 %" in resumen


class TestNormalizacion:
    @pytest.mark.parametrize(
        "texto, esperado",
        [
            ("Pimienta Negra", "pepper, black and green"),
            ("black pepper", "pepper, black and green"),
            ("Piper nigrum", "pepper, black and green"),
            ("apio", "celery"),
            ("Apium graveolens", "celery"),
            ("cúrcuma", "turmeric"),
            ("Zingiber officinale", "ginger"),
        ],
    )
    def test_sinonimos_bilingues_y_botanicos(self, texto, esperado):
        assert detect_family(texto) == esperado

    def test_alias_mas_largo_gana(self):
        """'black pepper' debe ganarle a 'pepper' a secas."""
        assert detect_family("white pepper oleoresin") == "pepper, white"

    def test_abreviaturas_se_expanden(self):
        assert "oleoresin" in normalize("OR Black Pepper")
        assert "water dispersible" in normalize("Black pepper WD")

    def test_acentos_se_ignoran(self):
        assert normalize("Cúrcuma") == normalize("curcuma")
