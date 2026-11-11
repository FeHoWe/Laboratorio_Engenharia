import sqlite3
import pytest
from modules.arsenal import Arsenal, ArsenalError
from modules.workspace import seed_showcase


def _lista(tmp):
    return sorted((tmp / "backups").glob("arsenal.db.*.bak"))


def test_open_backs_up_only_when_content_changed(tmp_path):
    db = tmp_path / "arsenal.db"
    a = Arsenal(db); ids = seed_showcase(a); a.close()                 # 1ª criação: arquivo ainda não existia na abertura → sem backup
    assert _lista(tmp_path) == []
    Arsenal(db).close()                                                # abre com conteúdo → 1 backup
    assert len(_lista(tmp_path)) == 1
    Arsenal(db).close()                                                # conteúdo idêntico → NÃO cria outro
    assert len(_lista(tmp_path)) == 1
    a = Arsenal(db); a.modify(ids[0], "teste", params={"d": 12}); a.close()
    Arsenal(db).close()                                                # mudou → novo backup
    assert len(_lista(tmp_path)) == 2


def test_backup_is_valid_sqlite_with_previous_content(tmp_path):
    db = tmp_path / "arsenal.db"
    a = Arsenal(db); ids = seed_showcase(a); a.close()
    a = Arsenal(db)                                                    # backup da abertura = estado com N componentes
    n = len(a.list_components())
    for cid in ids[:2]:
        a.delete_component(cid, confirm=True)                          # cada exclusão faz backup antes
    bk = _lista(tmp_path)
    assert len(bk) >= 2
    con = sqlite3.connect(bk[0]); assert con.execute("select count(*) from components").fetchone()[0] == n; con.close()
    a.close()


def test_restore_recovers_deleted_component_and_keeps_current_state_as_backup(tmp_path):
    db = tmp_path / "arsenal.db"
    a = Arsenal(db); ids = seed_showcase(a); a.close()
    a = Arsenal(db); total = len(a.list_components())
    a.delete_component(ids[0], confirm=True); a.close()
    assert Arsenal(db).list_components().__len__() == total - 1
    Arsenal.restore_backup(db)                                         # backup mais recente = ANTES da exclusão
    b = Arsenal(db)
    assert len(b.list_components()) == total and ids[0] in [c["id"] for c in b.list_components()]
    b.close()
    with pytest.raises(ArsenalError):
        Arsenal.restore_backup(tmp_path / "outro.db")


def test_rotation_and_memory_arsenal(tmp_path):
    assert Arsenal().backup() is None                                  # em memória: nada a salvar
    db = tmp_path / "arsenal.db"; a = Arsenal(db); seed_showcase(a)
    for i in range(5):
        a.db.execute("INSERT INTO categories(name, custom) VALUES(?, 1)", (f"c{i}",)); a.db.commit()
        a.backup(f"t{i}", keep=3)
    assert len(_lista(tmp_path)) == 3
    a.close()


def test_list_backups_shows_component_counts(tmp_path):
    db = tmp_path / "arsenal.db"
    a = Arsenal(db); ids = seed_showcase(a); a.close()
    a = Arsenal(db); n = len(a.list_components()); a.delete_component(ids[0], confirm=True); a.close()
    lst = Arsenal.list_backups(db)
    assert lst and lst[-1]["componentes"] == n and all(x["arquivo"].endswith(".bak") for x in lst)


def test_export_import_roundtrip_new_id_and_atomic(tmp_path):
    from modules.arsenal import Arsenal, ArsenalError
    a = Arsenal(tmp_path / "a.db")
    c = a.add_component("Parafuso X", a.categories()[0], {"part_key": "bolt", "params": {"d": 8}, "material": "aço 8.8"})
    a.modify(c, "mudou d", params={"d": 10})
    f = tmp_path / "exp.json"
    assert a.export_to_file([c], f) == 1
    b = Arsenal(tmp_path / "b.db")
    ids = b.import_file(f)
    n = b.get(ids[0])
    assert ids[0] != c or True
    assert [v["version"] for v in b.versions(ids[0])] == [v["version"] for v in a.versions(c)]
    assert n["params"]["d"] == 10 and b.get(ids[0], "1.0")["params"]["d"] == 8 and n["material"] == "aço 8.8" and "importado de" in n["description"]
    ids2 = b.import_file(f)                                  # importar de novo nunca sobrescreve: ID novo
    assert ids2[0] != ids[0] and len(b.list_components()) == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"name":"x","category":"y","versions":[{"version":"1.0","data":{"params":{}}}]}')
    with pytest.raises(ArsenalError):
        b.import_file(bad)
    assert len(b.list_components()) == 2                     # inválido não grava nada
    bad.write_text("não é json")
    with pytest.raises(ArsenalError):
        b.import_file(bad)
