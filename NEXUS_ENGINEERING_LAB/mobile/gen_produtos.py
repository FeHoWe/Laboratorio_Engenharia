"""Gera mobile/produtos.js a partir de core/products.py e modules/intelligence.py (uma única fonte da verdade)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import products as P
from modules import intelligence as I

def main() -> Path:
    prods = [{"chave": p.chave, "nome": p.nome, "missao": p.missao, "estado": p.estado(), "lacunas": list(p.lacunas),
              "caps": [{"rotulo": c.rotulo, "estado": c.estado, "nota": c.nota} for c in p.capacidades]} for p in P.PRODUTOS]
    out = ROOT / "mobile" / "produtos.js"
    out.write_text("window.__produtos=" + json.dumps(prods, ensure_ascii=False) + ";window.__glossario=" + json.dumps(I.GLOSSARIO, ensure_ascii=False) + ";", encoding="utf-8")
    return out

if __name__ == "__main__":
    print(main())
