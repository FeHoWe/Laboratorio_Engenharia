"""V4.1b — nomes persistentes de faces/arestas (rastreio pelo histórico do OpenCascade), revolução de esboço, variáveis/expressões/restrições."""
import math
import pytest
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt
from modules.cad_history import CadHistory, CadHistoryError, _bbox
from modules.sketch2d import Sketch


def box(a=40, b=40, c=10, o=(0, 0, 0)):
    return BRepPrimAPI_MakeBox(gp_Pnt(*o), a, b, c).Shape()


def area(f):
    p = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, p); return p.Mass()


TOPO = {"modo": "extrema", "lado": "+z"}


# ------------------------------------------------------------------ nomes persistentes
def test_nome_de_face_acompanha_transformacoes():
    h = CadHistory(box())
    h.nomear("topo", "face", TOPO)
    h.add("translate", dx=5, dy=0, dz=0)
    h.add("scale", factor=2)
    (f,) = h.entidades("topo")
    b = _bbox(f)
    assert b[2] == pytest.approx(20) and b[5] == pytest.approx(20)           # topo em z = 10·2
    assert area(f) == pytest.approx(80 * 80)


def test_nome_sobrevive_a_furo_na_propria_face_e_a_edicao_de_parametro():
    h = CadHistory(box())
    h.nomear("topo", "face", TOPO)
    i = h.add("hole", x=20, y=20, z=11, dx=0, dy=0, dz=-1, diameter=4, depth=12)
    (f,) = h.entidades("topo")
    assert area(f) == pytest.approx(1600 - math.pi * 4, abs=1e-6)             # a MESMA face, agora furada
    h.set_param(i, "diameter", 8)
    (f,) = h.entidades("topo")
    assert area(f) == pytest.approx(1600 - math.pi * 16, abs=1e-6)            # continua designada após editar a operação a montante


def test_nome_apagado_por_operacao_vira_erro_explicito():
    h = CadHistory(box())
    h.nomear("lado", "face", {"modo": "extrema", "lado": "+x"})
    h.add("box_add", x0=40, y0=0, z0=0, x1=60, y1=40, z1=10)                  # cola um bloco inteiro nessa face: ela some
    with pytest.raises(CadHistoryError, match="perdida"):
        h.entidades("lado")
    with pytest.raises(CadHistoryError, match="perdida"):
        h.add("shell", thickness=1, open_face="nome:lado")
    assert len(h.ops) == 1                                                    # a operação recusada não entrou


def test_filete_em_aresta_nomeada_depois_de_mover_a_peca():
    h = CadHistory(box())
    h.nomear("borda", "aresta", {"modo": "perto", "ponto": [20, 0, 10]})      # aresta de topo, y = 0
    h.add("rotate", px=0, py=0, pz=0, ax=0, ay=0, az=1, angle_deg=90)
    h.add("translate", dx=100, dy=0, dz=0)
    h.add("fillet", radius=2, edges="nome:borda")
    assert h.volume() == pytest.approx(16000 - (4 - math.pi) * 40, abs=1e-6)  # só UMA aresta de 40 mm arredondada


def test_casca_com_face_aberta_nomeada_apos_rotacao():
    h = CadHistory(box(40, 40, 20))
    h.nomear("tampa", "face", TOPO)
    h.add("rotate", px=0, py=0, pz=0, ax=1, ay=0, az=0, angle_deg=90)         # a tampa deixa de ser +z
    h.add("shell", thickness=2, open_face="nome:tampa")
    assert h.volume() == pytest.approx(40 * 40 * 20 - 36 * 36 * 18, abs=1e-4)


def test_nomes_validacao_e_serializacao():
    h = CadHistory(box())
    with pytest.raises(CadHistoryError): h.nomear("x y", "face", TOPO)
    with pytest.raises(CadHistoryError): h.nomear("a", "volume", TOPO)
    with pytest.raises(CadHistoryError): h.nomear("a", "face", {"modo": "bobagem"})
    assert h.nomes == {}
    h.nomear("topo", "face", TOPO); h.nomear("borda", "aresta", {"modo": "sel", "sel": "top:z"})
    with pytest.raises(CadHistoryError): h.nomear("topo", "face", TOPO)        # duplicado
    h.add("shell", thickness=2, open_face="nome:topo")
    v = h.volume()
    h2 = CadHistory.from_dict(h.to_dict(), box())
    assert h2.volume() == pytest.approx(v) and set(h2.nomes) == {"topo", "borda"}
    h3 = CadHistory.from_dict({"base_ref": "x", "ops": [], "cursor": 0}, box())   # arquivo antigo, sem nomes/vars
    assert h3.volume() == pytest.approx(16000)


def test_tipo_errado_e_perto_ambiguo():
    h = CadHistory(box())
    h.nomear("topo", "face", TOPO)
    with pytest.raises(CadHistoryError, match="precisa"):
        h.add("fillet", radius=1, edges="nome:topo")
    with pytest.raises(CadHistoryError, match="ambíguo"):
        h.nomear("m", "aresta", {"modo": "perto", "ponto": [20, 20, 10.0 + 0]})   # centro do topo: equidistante das 4 arestas


def test_desfazer_descarta_nomes_posteriores():
    h = CadHistory(box())
    h.add("translate", dx=1, dy=0, dz=0)
    h.undo()
    h.nomear("topo", "face", TOPO)                                            # ligado no passo 0 (cursor = 0)
    h.add("translate", dx=2, dy=0, dz=0)
    assert "topo" in h.nomes and h.nomes["topo"]["passo"] == 0


# ------------------------------------------------------------------ revolução de esboço
def _ret(x0, y0, x1, y1, plano="XY", off=0.0):
    sk = Sketch(plano, off); sk.add(t="rect", x0=x0, y0=y0, x1=x1, y1=y1); return sk.to_dict()


def test_revolucao_anel_completo_e_meio():
    h = CadHistory(box(1, 1, 1, (100, 100, 100)))
    h.add("sketch_revolve", sketch=_ret(5, 0, 10, 20), angle_deg=360, axis=[0, 0, 0, 1], mode="add")
    assert h.volume() == pytest.approx(1 + math.pi * (100 - 25) * 20, rel=1e-9)     # tubo: π(R²−r²)·h
    h2 = CadHistory(box(1, 1, 1, (100, 100, 100)))
    h2.add("sketch_revolve", sketch=_ret(5, 0, 10, 20), angle_deg=180, axis=[0, 0, 0, 1], mode="add")
    assert h2.volume() == pytest.approx(1 + math.pi * (100 - 25) * 20 / 2, rel=1e-9)


def test_revolucao_corte_cilindrico_e_erros():
    h = CadHistory(box())
    h.add("sketch_revolve", sketch=_ret(20, 0, 24, 40, off=5), angle_deg=360, axis=[20, 0, 20, 1], mode="cut")
    assert h.volume() == pytest.approx(16000 - math.pi * 16 * 40, rel=1e-9)
    for kw in (dict(angle_deg=0, axis=[0, 0, 0, 1]), dict(angle_deg=400, axis=[0, 0, 0, 1]), dict(angle_deg=90, axis=[1, 1, 1, 1]), dict(angle_deg=90, axis=[0, 0, 1])):
        with pytest.raises(CadHistoryError):
            h.add("sketch_revolve", sketch=_ret(5, 0, 10, 20), mode="add", **kw)
    assert len(h.ops) == 1


# ------------------------------------------------------------------ variáveis, expressões e restrições
def test_variavel_e_referencia_entre_operacoes():
    h = CadHistory(box())
    h.definir("D", 4)
    h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=D", depth=12)
    assert h.volume() == pytest.approx(16000 - math.pi * 4 * 10)
    h.add("counterbore", x=10, y=10, z=10, dx=0, dy=0, dz=-1, diameter="=op[0].diameter", depth=10, cb_diameter="=op[0].diameter*2", cb_depth=3)
    v1 = h.volume()
    h.definir("D", 6)                                                         # muda UMA variável: os dois furos acompanham
    assert h.volume() < v1
    esperado = 16000 - math.pi * 9 * 10 - (math.pi * 36 * 3 + math.pi * 9 * 7)
    assert h.volume() == pytest.approx(esperado, abs=1e-6)
    h.set_param(0, "diameter", 5)                                             # o escareado referencia op[0].diameter
    assert h.ops[1]["params"]["diameter"] == "=op[0].diameter"


def test_restricoes_desfazem_edicao_invalida():
    h = CadHistory(box())
    i = h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter=4, depth=12)
    h.restringir("op[0].diameter < 10")
    h.restringir("volume > 10000 and dz == 10")
    with pytest.raises(CadHistoryError, match="violada"):
        h.set_param(i, "diameter", 12)
    assert h.ops[i]["params"]["diameter"] == 4                                # revertido
    with pytest.raises(CadHistoryError, match="violada"):
        h.restringir("volume > 100000")
    assert len(h.restricoes) == 2
    with pytest.raises(CadHistoryError, match="comparação"):
        h.restringir("op[0].diameter + 1")
    assert len(h.restricoes) == 2


def test_expressoes_sao_seguras_e_ciclos_detectados():
    h = CadHistory(box())
    i = h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter=4, depth=12)
    for ruim in ("=__import__('os').getcwd()", "=open('x')", "=op[0].__class__", "=desconhecida*2", "=1/0", "=(lambda: 1)()", "=2 +"):
        with pytest.raises(CadHistoryError):
            h.set_param(i, "diameter", ruim)
        assert h.ops[i]["params"]["diameter"] == 4
    j = h.add("hole", x=5, y=5, z=-1, dx=0, dy=0, dz=1, diameter="=op[0].diameter", depth=12)
    with pytest.raises(CadHistoryError, match="circular"):
        h.set_param(i, "diameter", "=op[1].diameter")
    assert h.ops[i]["params"]["diameter"] == 4 and j == 1


def test_funcoes_permitidas_e_serializacao_de_vars():
    h = CadHistory(box())
    h.definir("L", 16)
    h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=sqrt(L)+min(1,2)-1", depth=12)   # sqrt(16)=4
    assert h.volume() == pytest.approx(16000 - math.pi * 4 * 10)
    h.restringir("L > 1")
    h2 = CadHistory.from_dict(h.to_dict(), box())
    assert h2.vars == {"L": 16.0} and h2.restricoes == ["L > 1"] and h2.volume() == pytest.approx(h.volume())
    with pytest.raises(CadHistoryError): h.definir("pi", 3)
    with pytest.raises(CadHistoryError): h.definir("a b", 3)


def test_dialogos_constroem_e_revolucao_pelo_dialogo():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.cad_history_dialog import CadHistoryDialog
    from interface.sketch_dialog import SketchDialog
    d = CadHistoryDialog(); d.hist = CadHistory(box(1, 1, 1, (100, 100, 100)))
    sd = SketchDialog(d, d.hist)
    sd.sk.add(t="rect", x0=5, y0=0, x1=10, y1=20)
    sd.apply_revolve()
    assert d.hist.ops[-1]["type"] == "sketch_revolve" and d.hist.volume() > 1000
    d.refresh()
    assert "sketch_revolve" in d.lst.item(0).text()


# ------------------------------------------------------------------ V5.3: ajuste de uma variável a um alvo
def test_ajustar_diametro_para_atingir_volume():
    h = CadHistory(box())
    h.definir("D", 2)
    h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=D", depth=12)
    r = h.ajustar("D", "volume", 15000, 0.5, 30)
    assert h.vars["D"] == pytest.approx(r["valor"]) and h.volume() == pytest.approx(15000, abs=1e-3)
    assert r["valor"] == pytest.approx(2 * math.sqrt(1000 / (math.pi * 10)), rel=1e-6)          # π(D/2)²·10 = 1000
    assert abs(r["obtido"] - 15000) < 1e-3


def test_ajustar_dimensao_da_caixa_envolvente():
    h = CadHistory(box())
    h.definir("L", 5)
    h.add("box_add", x0=40, y0=0, z0=0, x1="=40+L", y1=40, z1=10)
    h.ajustar("L", "dx", 70, 1, 100)
    assert h.vars["L"] == pytest.approx(30, abs=1e-5)


def test_ajustar_recusa_fora_da_faixa_e_nao_altera_nada():
    h = CadHistory(box())
    h.definir("D", 2)
    h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=D", depth=12)
    h.restringir("D < 20")
    with pytest.raises(CadHistoryError, match="não está entre"):
        h.ajustar("D", "volume", 1000, 0.5, 30)                    # com o furo máximo o volume ainda é > 1000
    with pytest.raises(CadHistoryError, match="não existe"):
        h.ajustar("X", "volume", 1, 0, 1)
    with pytest.raises(CadHistoryError, match="métrica"):
        h.ajustar("D", "massa", 1, 0, 1)
    with pytest.raises(CadHistoryError, match="faixa"):
        h.ajustar("D", "volume", 1, 5, 1)
    assert h.vars["D"] == 2 and h.restricoes == ["D < 20"]


def test_ajustar_respeita_restricoes_ao_aplicar():
    h = CadHistory(box())
    h.definir("D", 2)
    h.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=D", depth=12)
    h.restringir("D < 5")
    with pytest.raises(CadHistoryError, match="violada"):
        h.ajustar("D", "volume", 15000, 0.5, 30)                   # a solução (≈11,3) viola D < 5
    assert h.vars["D"] == 2


def test_ajustar_geometria_invalida_na_faixa_e_reportada():
    h = CadHistory(box())
    h.definir("R", 1)
    h.add("fillet", radius="=R", edges="all")
    with pytest.raises(CadHistoryError, match="falha com R"):
        h.ajustar("R", "volume", 15000, 0.5, 50)                    # R = 50 não cabe numa caixa de 10 mm
    assert h.vars["R"] == 1


def test_textos_das_caixas_do_editor_cad_estao_traduzidos_nos_5_idiomas():
    """V5.4 — todo tr("…") literal dos diálogos do editor CAD tem tradução em en/es/de/fr/zh (os 10 outros caem para o inglês)."""
    import ast, json
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    textos = set()
    for f in ("interface/cad_history_dialog.py", "interface/sketch_dialog.py"):
        for n in ast.walk(ast.parse((raiz / f).read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tr" and n.args and isinstance(n.args[0], ast.Constant):
                textos.add(n.args[0].value)
    assert len(textos) > 40
    for lang in ("en", "es", "de", "fr", "zh"):
        cat = json.loads((raiz / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        falta = [t for t in textos if t not in cat]
        assert not falta, (lang, falta)


def test_ajustar_pelo_dialogo(monkeypatch):
    from PySide6.QtWidgets import QApplication, QInputDialog
    QApplication.instance() or QApplication([])
    from interface.cad_history_dialog import CadHistoryDialog
    d = CadHistoryDialog(); d.hist = CadHistory(box()); d.hist.definir("D", 2)
    d.hist.add("hole", x=20, y=20, z=-1, dx=0, dy=0, dz=1, diameter="=D", depth=12)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (a[3][0], True)))
    vals = iter([15000.0, 0.5, 30.0])
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (next(vals), True)))
    d.ajustar()
    assert d.hist.volume() == pytest.approx(15000, abs=1e-3) and "D =" in d.info.text()
