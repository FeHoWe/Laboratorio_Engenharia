import pytest
from modules.arsenal import Arsenal, ArsenalError
from modules.workspace import seed_showcase, PartHistory, ProjectStore
from modules.result_trace import TracedResult
from samples.library import PARTS

def test_seed_idempotent_and_no_material():
    a = Arsenal(); ids = seed_showcase(a)
    assert len(ids) == len(PARTS) and seed_showcase(a) == []
    assert all(a.get(i)["material"] is None for i in ids)

def test_history_undo_redo_and_build():
    h = PartHistory.new("flange", od=140)
    h.set_param("bolts", 8)
    assert h.params["bolts"] == 8 and h.undo() and h.params["bolts"] == 6 and h.redo() and h.params["bolts"] == 8
    h.undo(); h.set_param("bolts", 4); assert not h.redo()          # ramo redo descartado
    with pytest.raises(ValueError): h.set_param("od", 1)
    assert h.build() is not None
    assert PartHistory.from_dict(h.to_dict()).params == h.params

def test_project_roundtrip_usage_and_delete(tmp_path):
    a = Arsenal(); ids = seed_showcase(a); s = ProjectStore(tmp_path)
    p = s.create("meu"); 
    with pytest.raises(FileExistsError): s.create("meu")
    s.add_from_arsenal(p, a, ids[0], {"d": 10})
    q = s.open("meu"); assert q["parts"][0]["params"]["d"] == 10 and q["parts"][0]["arsenal_id"] == ids[0]
    assert a.get(ids[0])["params"]["d"] != 10                      # original intacto
    assert s.usage(ids[0]) == ["meu"]
    with pytest.raises(ArsenalError): s.delete_arsenal_component(a, ids[0], confirm=True)   # em uso
    with pytest.raises(ArsenalError): s.delete_arsenal_component(a, ids[1])                 # sem confirmação
    s.delete_arsenal_component(a, ids[1], confirm=True)
    assert ids[1] not in [c["id"] for c in a.list_components()]
    s.attach_result(q, TracedResult("t", "ANALITICO", "m")); assert s.open("meu")["results"][0]["classe"] == "ANALITICO"
    with pytest.raises(PermissionError): s.delete("meu")
    s.delete("meu", confirm=True); assert s.list() == []

def test_export_keeps_history():
    a = Arsenal(); cid = seed_showcase(a)[0]; a.modify(cid, "teste", params={"d": 12})
    e = a.export_component(cid); assert len(e["versions"]) == 2

def test_solvers_dialog_report():
    from interface.solvers_dialog import solver_report
    t = solver_report(); assert "NEXUS-Tet4" in t and "CalculiX" in t
