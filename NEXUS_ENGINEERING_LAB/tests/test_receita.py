"""V100 — receitas em lote (módulo, CLI e diálogo)."""
import io, json
import pytest
import nexus_cli
from modules import dossie, receita as R

CARRO = dict(massa=800.0, p_ice=500e3, cda=1.0, cla=3.0, mu=1.6, p_ers=300e3, e_ers=4e6)
REC = {"titulo": "lote", "passos": [{"nome": "base", "tipo": "volta", "parametros": {"carro": CARRO}},
                                     {"nome": "sens", "tipo": "tornado", "parametros": {"carro": CARRO, "campos": ["massa"], "pct": 5}}]}


def test_executa_grava_e_dossies_verificam(tmp_path):
    rs = R.executar(json.loads(json.dumps(REC)), tmp_path / "o")
    assert rs["ok"] and [x["nome"] for x in rs["passos"]] == ["base", "sens"]
    for x in rs["passos"]:
        assert dossie.verificar(dossie.carregar(tmp_path / "o" / x["arquivo"]))["reproduziu"]
    assert (tmp_path / "o" / "resumo.json").exists() and "2/2 passos ok" in (tmp_path / "o" / "resumo.txt").read_text(encoding="utf-8")


def test_passo_com_erro_nao_derruba_lote(tmp_path):
    r = json.loads(json.dumps(REC)); r["passos"].insert(1, {"nome": "ruim", "tipo": "volta", "parametros": {"carro": {"zzz": 1}}})
    rs = R.executar(r, tmp_path)
    assert not rs["ok"] and [x["ok"] for x in rs["passos"]] == [True, False, True] and "carro" in rs["passos"][1]["erro"]


def test_validacao():
    for bad in ({}, {"passos": []}, {"passos": [{"tipo": "xx", "parametros": {}}]}, {"passos": [{"tipo": "volta"}]},
                {"passos": [{"nome": "a", "tipo": "volta", "parametros": {}}, {"nome": "a", "tipo": "volta", "parametros": {}}]}):
        with pytest.raises(R.ReceitaError): R.validar(bad)
    with pytest.raises(R.ReceitaError, match="não foi possível ler"): R.ler("/nao/existe.json")
    r = {"passos": [{"nome": "../x y", "tipo": "volta", "parametros": {}}]}; R.validar(r)
    assert r["passos"][0]["nome"] == "___x_y"                      # nome saneado: sem barra, não escapa da pasta


def test_cli(tmp_path):
    arq = tmp_path / "r.json"; arq.write_text(json.dumps(REC))
    buf = io.StringIO()
    assert nexus_cli.executar(["--json", "receita", str(arq), "--pasta", str(tmp_path / "s")], out=buf) == 0
    assert json.loads(buf.getvalue())["ok"] is True
    ruim = dict(REC, passos=[{"nome": "x", "tipo": "volta", "parametros": {"carro": {"q": 1}}}]); arq.write_text(json.dumps(ruim))
    assert nexus_cli.executar(["receita", str(arq), "--pasta", str(tmp_path / "s2")], out=io.StringIO()) == 1
    assert nexus_cli.executar(["receita", str(tmp_path / "nao.json")], out=io.StringIO()) == 1


def test_dialogo_executa_receita(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QFileDialog
    from interface.f1_dialog import F1Dialog
    QApplication.instance() or QApplication([])
    arq = tmp_path / "r.json"; arq.write_text(json.dumps(REC))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(arq), ""))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path / "gui"))
    d = F1Dialog(None)
    d.executar_receita()
    assert "2/2 passos ok" in d.st_out.toPlainText() and (tmp_path / "gui" / "resumo.json").exists()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    d.st_out.setPlainText("x"); d.executar_receita(); assert d.st_out.toPlainText() == "x"
