from types import SimpleNamespace

from modules import intelligence as I
from modules import intelligence_llm as L
from modules.result_trace import TracedResult


def _parecer():
    return I.interpretar(TracedResult("FEA", "SIMULACAO_NUMERICA", "m", {"vm_max_MPa": 300.0, "fator_seguranca_escoamento_ref": 0.83}, {"malhador": "gmsh", "ordem": 2},
                                      solver="s", solver_versao="1"))


def _fake(resposta):
    msgs = []
    def create(**kw):
        msgs.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(text=resposta)])
    return SimpleNamespace(messages=SimpleNamespace(create=create)), msgs


def test_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = L.perguntar("o que fazer?", _parecer())
    assert r["disponivel"] is False and "ANTHROPIC_API_KEY" in r["motivo"] and not r["aprovada"]


def test_grounded_answer_is_approved_and_prompt_carries_only_facts():
    cli, msgs = _fake("O fator de segurança é 0.83 (valores.fator_seguranca_escoamento_ref), logo há escoamento previsto; reduza a carga.")
    r = L.perguntar("Posso usar essa peça?", _parecer(), cliente=cli)
    assert r["disponivel"] and r["aprovada"] and not r["numeros_sem_fundamento"]
    assert "0.83" in msgs[0]["messages"][0]["content"] and "NÃO introduza nenhum número" in msgs[0]["system"]


def test_invented_numbers_are_flagged():
    cli, _ = _fake("O fator de segurança é 0.83, mas com aço 1045 você teria 2.4 e a vida em fadiga seria 1,2e6 ciclos.")
    r = L.perguntar("E se trocar o material?", _parecer(), cliente=cli)
    assert not r["aprovada"] and "2.4" in r["numeros_sem_fundamento"] and "ATENÇÃO" in r["aviso"]


def test_number_check_tolerances():
    assert L.verificar_numeros("vm = 300,0 MPa e FS 0,83", "von Mises 300.0 FS 0.83") == []
    assert L.verificar_numeros("valor 301 MPa", "von Mises 300.0") == []                 # 0,33 % de arredondamento
    assert L.verificar_numeros("valor 320 MPa", "von Mises 300.0") == ["320"]
    assert L.verificar_numeros("são 3 itens", "") == []                                    # inteiros pequenos tolerados
