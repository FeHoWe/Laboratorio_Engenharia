import pytest
from modules.arsenal import Arsenal, ArsenalError, check_compatibility, NOT_VERIFIED, NOT_INFORMED


def make():
    a = Arsenal()
    cid = a.add_component("Eixo principal", "Componentes mecânicos",
                          {"part_key": "stepped_shaft", "params": {"d1": 20}, "interfaces": [{"kind": "shaft", "d": 20, "id": "mancal"}]})
    return a, cid


def test_ids_and_versions_never_overwrite():
    a, cid = make()
    assert cid == "NEXUS-COMP-000001"
    assert a.add_component("Outro", "Componentes mecânicos", {"part_key": "bushing"}) == "NEXUS-COMP-000002"
    v = a.modify(cid, "Alteração de diâmetro", params={"d1": 22})
    assert v == "1.1"
    assert a.get(cid, "1.0")["params"]["d1"] == 20 and a.get(cid)["params"]["d1"] == 22
    assert [x["version"] for x in a.versions(cid)] == ["1.0", "1.1"]
    with pytest.raises(ArsenalError):
        a.modify(cid, "nada", params={"d1": 22})


def test_compare_restore_duplicate():
    a, cid = make()
    a.modify(cid, "d", params={"d1": 22})
    assert a.compare(cid, "1.0", "1.1") == [{"campo": "params.d1", "de": 20, "para": 22}]
    v = a.restore(cid, "1.0")
    assert v == "1.2" and a.get(cid)["params"]["d1"] == 20 and len(a.versions(cid)) == 3
    dup = a.duplicate(cid, "Eixo variante")
    assert dup != cid and a.get(dup)["parent"] == (cid, "1.2")


def test_instantiate_does_not_change_original():
    a, cid = make()
    inst = a.instantiate(cid, overrides={"d1": 30})
    assert inst["params"]["d1"] == 30 and "modificações locais" in inst["origin"]
    assert a.get(cid)["params"]["d1"] == 20


def test_material_not_invented_and_property_provenance():
    a, cid = make()
    assert a.get(cid)["material_label"] == NOT_INFORMED
    with pytest.raises(ArsenalError):
        a.modify(cid, "x", properties={"massa": {"value": 1.0}})
    a.modify(cid, "massa medida", properties={"massa": {"value": 1.0, "unit": "kg", "origin": "medido"}})


def test_categories_custom_and_errors():
    a, _ = make()
    a.add_category("Meus protótipos")
    assert "Meus protótipos" in a.categories()
    with pytest.raises(ArsenalError):
        a.add_component("x", "Inexistente", {"part_key": "bushing"})
    with pytest.raises(ArsenalError):
        a.add_component("x", "Meus protótipos", {})


def test_compatibility():
    shaft = {"interfaces": [{"kind": "shaft", "d": 20, "id": "eixo"}]}
    bore = {"interfaces": [{"kind": "bore", "d": 20.02, "id": "furo"}]}
    big = {"interfaces": [{"kind": "bore", "d": 25, "id": "furo"}]}
    assert check_compatibility(shaft, bore)["status"].startswith("COMPATÍVEL")
    assert check_compatibility(shaft, big)["status"] == "INCOMPATÍVEL"
    assert check_compatibility(shaft, {})["status"] == NOT_VERIFIED
    thr = {"interfaces": [{"kind": "thread_ext", "d": 8, "id": "M8"}]}
    thr2 = {"interfaces": [{"kind": "thread_int", "d": 8, "id": "M8i"}]}
    assert check_compatibility(thr, thr2)["status"] == NOT_VERIFIED  # passo não informado
