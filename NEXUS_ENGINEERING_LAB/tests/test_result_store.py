import pytest
from modules.arsenal import Arsenal
from modules.result_store import ResultStore, compare, fingerprint_recipe, fingerprint_shape
from modules.result_trace import TracedResult
from modules.workspace import ProjectStore, seed_showcase
from samples.library import PARTS


def test_recipe_fingerprint_deterministic_and_sensitive():
    a = fingerprint_recipe("flange", {"od": 140.0, "bolts": 6})
    assert a == fingerprint_recipe("flange", {"bolts": 6, "od": 140.0})
    assert a != fingerprint_recipe("flange", {"od": 140.5, "bolts": 6})
    assert a != fingerprint_recipe("flange", {"od": 140.0, "bolts": 6}, version="1.1")


def test_shape_fingerprint_detects_change_but_not_rebuild():
    s1 = PARTS["tubo_redondo"].make(length=100, od=40, t=5)
    s2 = PARTS["tubo_redondo"].make(length=100, od=40, t=5)
    s3 = PARTS["tubo_redondo"].make(length=100, od=40, t=6)
    assert fingerprint_shape(s1) == fingerprint_shape(s2) != fingerprint_shape(s3)


def test_geometry_change_obsoletes_results_but_preserves_them(tmp_path):
    a = Arsenal(); ids = seed_showcase(a); st = ProjectStore(tmp_path)
    p = st.create("proj"); st.add_from_arsenal(p, a, ids[0])
    fp = st.part_fingerprints(p); label = next(iter(fp))
    r = TracedResult("estudo", "ANALITICO", "m", {"u_max_mm": 1.0})
    st.attach_result(p, r, fp[label], label)
    assert st.refresh_results(p) == [] and len(ResultStore(p).vigentes()) == 1
    k = next(iter(p["parts"][0]["params"]))
    p["parts"][0]["params"][k] = p["parts"][0]["params"][k] * 1.1                 # geometria alterada
    ch = st.refresh_results(p)
    q = st.open("proj")
    assert len(ch) == 1 and q["results"][0]["status_geometria"] == "OBSOLETO" and "versão anterior" in q["results"][0]["obsoleto_motivo"]
    assert q["results"][0]["valores"]["u_max_mm"] == 1.0                           # histórico preservado
    # novo resultado para a nova geometria é vigente; o antigo continua obsoleto
    fp2 = st.part_fingerprints(p)
    st.attach_result(p, TracedResult("estudo", "ANALITICO", "m", {"u_max_mm": 1.3}), fp2[label], label)
    rs = ResultStore(st.open("proj"))
    assert len(rs.vigentes()) == 1 and len(rs.obsoletos()) == 1


def test_legacy_results_without_link_are_not_claimed_valid(tmp_path):
    st = ProjectStore(tmp_path); p = st.create("x")
    st.attach_result(p, TracedResult("antigo", "ANALITICO", "m"))
    ResultStore(p).refresh({})
    assert p["results"][0]["status_geometria"] == "SEM_VINCULO"


def test_compare_versions():
    a = {"valores": {"u": 1.0, "k": 2, "nome": "x"}, "geometry_fp": "A", "metodo": "m", "status_geometria": "OBSOLETO"}
    b = {"valores": {"u": 1.2, "k": 2, "nome": "y"}, "geometry_fp": "B", "metodo": "m", "status_geometria": "VIGENTE"}
    c = compare(a, b)
    assert not c["mesma_geometria"] and c["mesmo_metodo"]
    u = next(l for l in c["linhas"] if l["grandeza"] == "u")
    assert u["delta"] == pytest.approx(0.2) and u["delta_pct"] == pytest.approx(20.0)
    assert {l["grandeza"] for l in c["linhas"]} == {"u", "k"}
