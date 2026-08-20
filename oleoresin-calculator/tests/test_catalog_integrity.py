"""Integridad del catálogo y del motor de recomendación.

El test más importante de todo el repo es ``test_ningun_anulado_es_ofertable``:
el ASKRC marca 'Void / Do Not Sample' con **tachado de fuente**, que
``pandas.read_excel`` descarta en silencio. Sin esta verificación, la app puede
recomendar producto descontinuado con total confianza y sin señal de alarma.
"""
import pytest

from data_layer.schema import (
    SOURCE_EXTENDED,
    SOURCE_FIRST_CHOICE,
    STATUS_ACTIVE,
    STATUS_CONVERTED,
    STATUS_VOID,
    Product,
)
from data_layer.catalog import Catalog, merge
from core.units import SpecRange
from matching.scorer import lookup_code, recommend
from matching.spec_parser import parse
from ui.i18n import check_parity


def make(code, source=SOURCE_EXTENDED, status=STATUS_ACTIVE, **kwargs):
    return Product(code=code, description=kwargs.pop("description", code),
                   source=source, status=status, **kwargs)


class TestExclusionDeAnulados:
    def test_ningun_anulado_es_ofertable(self):
        catalog = Catalog(products=[
            make("A1", status=STATUS_ACTIVE),
            make("A2", status=STATUS_VOID),
            make("A3", status=STATUS_CONVERTED, converted_to="A1"),
        ])
        codes = {p.code for p in catalog.offerable}
        assert codes == {"A1"}

    def test_el_recomendador_nunca_propone_un_anulado(self):
        analytes = {"piperine": SpecRange(38.0, 42.0, "range", "%")}
        catalog = Catalog(products=[
            make("VOID1", status=STATUS_VOID, family="pepper, black and green",
                 description="Black Pepper Oleoresin", solubility="oil", analytes=dict(analytes)),
            make("CONV1", status=STATUS_CONVERTED, converted_to="OK1",
                 family="pepper, black and green",
                 description="Black Pepper Oleoresin", solubility="oil", analytes=dict(analytes)),
            make("OK1", family="pepper, black and green",
                 description="Black Pepper Oleoresin", solubility="oil", analytes=dict(analytes)),
        ])
        spec = parse("Black Pepper Oleoresin, oil soluble, piperine 35% min")
        codes = [c.product.code for c in recommend(spec, catalog, limit=10)]
        assert codes == ["OK1"]
        assert "VOID1" not in codes and "CONV1" not in codes

    def test_buscar_un_anulado_avisa_en_vez_de_devolverlo_callado(self):
        catalog = Catalog(products=[make("VOID1", status=STATUS_VOID)])
        result = lookup_code("VOID1", catalog)
        assert result.found
        assert "Void" in result.message

    def test_buscar_un_reemplazado_devuelve_el_vigente(self):
        catalog = Catalog(products=[
            make("OLD1", status=STATUS_CONVERTED, converted_to="NEW1"),
            make("NEW1", status=STATUS_ACTIVE),
        ])
        result = lookup_code("OLD1", catalog)
        assert result.replacement is not None
        assert result.replacement.code == "NEW1"

    def test_cadena_circular_de_reemplazos_no_cuelga(self):
        catalog = Catalog(products=[
            make("A", status=STATUS_CONVERTED, converted_to="B"),
            make("B", status=STATUS_CONVERTED, converted_to="A"),
        ])
        assert lookup_code("A", catalog).replacement is None


class TestMerge:
    def test_first_choice_gana_ante_duplicidad(self):
        fc = [make("X1", source=SOURCE_FIRST_CHOICE, description="Ficha First Choice")]
        ex = [make("X1", source=SOURCE_EXTENDED, description="Ficha ASKRC")]
        merged = merge(fc, ex)
        assert len(merged) == 1
        assert merged[0].source == SOURCE_FIRST_CHOICE
        assert merged[0].description == "Ficha First Choice"

    def test_el_askrc_completa_los_marcadores_que_faltan(self):
        fc = [make("X1", source=SOURCE_FIRST_CHOICE, analytes={})]
        ex = [make("X1", source=SOURCE_EXTENDED,
                   analytes={"piperine": SpecRange(37.0, 40.0, "range", "%")})]
        merged = merge(fc, ex)
        assert "piperine" in merged[0].analytes

    def test_el_askrc_no_pisa_un_marcador_existente(self):
        fc = [make("X1", source=SOURCE_FIRST_CHOICE,
                   analytes={"piperine": SpecRange(37.0, 40.0, "range", "%")})]
        ex = [make("X1", source=SOURCE_EXTENDED,
                   analytes={"piperine": SpecRange(10.0, 12.0, "range", "%")})]
        assert merge(fc, ex)[0].analytes["piperine"].low == 37.0

    def test_la_anulacion_del_askrc_se_respeta(self):
        """First Choice manda en identidad, pero el ASKRC lleva la vigencia."""
        fc = [make("X1", source=SOURCE_FIRST_CHOICE, status=STATUS_ACTIVE)]
        ex = [make("X1", source=SOURCE_EXTENDED, status=STATUS_VOID)]
        assert merge(fc, ex)[0].status == STATUS_VOID


class TestSolubilidad:
    def test_misma_familia_distinta_solubilidad_no_es_el_mismo_producto(self):
        """Albahaca oil soluble 19-21 % vs dispersable 2-4 %: factor 7x distinto."""
        catalog = Catalog(products=[
            make("OIL", family="basil", description="Basil Oleoresin", solubility="oil",
                 analytes={"volatile_oil": SpecRange(19.0, 21.0, "range", "%")}),
            make("WD", family="basil", description="Basil Oleoresin",
                 solubility="water_dispersible",
                 analytes={"volatile_oil": SpecRange(2.0, 4.0, "range", "%")}),
        ])
        spec = parse("Basil oleoresin, oil soluble, volatile oil 18% min")
        best = recommend(spec, catalog, limit=5)
        assert best[0].product.code == "OIL"

        # La dispersable o se descarta por score, o aparece marcada como
        # bloqueante — lo que nunca puede es presentarse como equivalente.
        wd = next((c for c in best if c.product.code == "WD"), None)
        assert wd is None or (wd.blocking >= 1 and wd.confidence == "low")

    def test_la_dispersable_gana_cuando_es_la_que_se_pide(self):
        catalog = Catalog(products=[
            make("OIL", family="basil", description="Basil Oleoresin", solubility="oil",
                 analytes={"volatile_oil": SpecRange(19.0, 21.0, "range", "%")}),
            make("WD", family="basil", description="Basil Oleoresin",
                 solubility="water_dispersible",
                 analytes={"volatile_oil": SpecRange(2.0, 4.0, "range", "%")}),
        ])
        spec = parse("Basil oleoresin, water dispersible, volatile oil 2-4%")
        assert recommend(spec, catalog, limit=2)[0].product.code == "WD"


class TestSerializacion:
    def test_ida_y_vuelta_conserva_los_analitos(self):
        product = make("X1", analytes={"colour": SpecRange(40000.0, 41000.0, "range", "CU", "raw")})
        restored = Product.from_row(product.to_row())
        assert restored.analytes["colour"].low == 40000.0
        assert restored.analytes["colour"].unit == "CU"
        assert restored.status == product.status


class TestLocalizacion:
    def test_todas_las_claves_estan_en_ambos_idiomas(self):
        """La versión anterior tenía dos diccionarios paralelos a mano."""
        assert check_parity() == []
