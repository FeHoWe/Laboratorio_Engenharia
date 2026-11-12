import math
import pytest
from modules.units import Quantity, UnitError, convert


@pytest.mark.parametrize("v,a,b,exp", [
    (1, "in", "mm", 25.4), (100, "km/h", "m/s", 27.7777777778), (1, "bar", "Pa", 1e5), (1, "psi", "kPa", 6.894757293), (1, "hp", "kW", 0.7456998716),
    (0, "°C", "K", 273.15), (212, "°F", "°C", 100.0), (-40, "°C", "°F", -40.0), (3000, "rpm", "rad/s", 314.159265359), (1, "gn", "m/s²", 9.80665),
    (1, "kWh", "J", 3.6e6), (1, "gal(US)", "L", 3.785411784), (7850, "kg/m³", "g/cm³", 7.85), (1, "L", "cm³", 1000.0), (500, "N·mm", "N·m", 0.5)])
def test_known_conversions(v, a, b, exp):
    assert convert(v, a, b) == pytest.approx(exp, rel=1e-9)


def test_round_trip_all_units():
    from modules.units import TABLE
    for d, us in TABLE.items():
        for a in us:
            for b in us:
                assert convert(convert(12.345, a, b), b, a) == pytest.approx(12.345, rel=1e-12)


def test_incompatible_and_unknown():
    with pytest.raises(UnitError, match="incompatíveis"):
        convert(1, "kg", "m")
    with pytest.raises(UnitError, match="desconhecida"):
        convert(1, "furlong", "m")


def test_quantity_provenance():
    q = Quantity(100.0, "km/h", "documentado", "catálogo X")
    assert str(q.to("m/s")).startswith("27.7778 m/s [VALOR DOCUMENTADO, catálogo X]")
    assert str(Quantity(None, "kg")) == "PROPRIEDADE NÃO INFORMADA"
    with pytest.raises(UnitError):
        Quantity(None, "kg", "estimado")          # não inventa valor ausente
    with pytest.raises(UnitError):
        Quantity(1.0, "kg", "chute")
