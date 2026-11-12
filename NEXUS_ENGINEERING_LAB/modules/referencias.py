"""Banco de casos de referência com SELO por módulo (V3.6).

Cada caso compara o módulo com uma solução analítica/identidade conhecida. Selo: CONFERIDO (todos os casos do módulo dentro da tolerância), FALHOU,
ou NAO_EXECUTADO (precisa de solver ausente). IMPORTANTE: o selo mede coerência com a teoria nos casos listados — NÃO é validação contra ensaio, não cobre
todos os usos e não vale para CFD (nenhum caso de CFD roda aqui: é lento; veja os estudos de malha). Rodar: `python -m modules.referencias`.
"""
from __future__ import annotations

import math
from . import solver_registry as sr


def _caso(modulo, nome, esperado, obtido, tol_rel):
    ok = math.isfinite(obtido) and abs(obtido - esperado) <= tol_rel * max(abs(esperado), 1e-12)
    return {"modulo": modulo, "caso": nome, "esperado": esperado, "obtido": obtido, "tol_rel": tol_rel, "ok": bool(ok), "estado": "ok" if ok else "falhou"}


def rodar() -> dict:
    C = []
    from . import structural as st, vehicle_lateral as vl, tire_combined as tc, suspension as su, sketch2d as sk, fatigue as fa
    s = st.rect(10, 20)
    d = st.beam("cant_end", 100.0, 100.0, 210000.0, s)
    C.append(_caso("Estrutural (vigas)", "balanço, carga na ponta: δ=PL³/3EI", 100 * 100 ** 3 / (3 * 210000 * s.inertia), d["deflection"] if "deflection" in d else list(d.values())[0], 1e-9))
    v = vl.exemplo_ilustrativo()
    fz, mu, c = 4000.0, 1.5, 60000.0
    C.append(_caso("Veículo (pneu)", "pneu: pequeno α → Fy ≈ C·α", c * 1e-4, vl.pneu_fy(1e-4, fz, c, mu), 1e-3))
    C.append(_caso("Veículo (pneu)", "pneu combinado, κ=0 ≡ modelo lateral", vl.pneu_fy(0.05, fz, c, mu), tc.forca_combinada(0.0, 0.05, fz, c, c, mu)[1], 1e-9))
    fx, fy = tc.forca_combinada(0.8, 0.5, fz, c, c, mu)
    C.append(_caso("Veículo (pneu)", "saturação: |F| = μ·Fz", mu * fz, math.hypot(fx, fy), 1e-9))
    ex = su.exemplo_ilustrativo(); r = su.resolver(ex, 0.01)
    C.append(_caso("Veículo (suspensão)", "|ganho de camber| ≈ 1/FVSA", 1.0 / r["FVSA_m"], abs(su.resolver(ex, 0.011)["camber_graus"] - su.resolver(ex, 0.009)["camber_graus"]) / 0.002 * math.pi / 180, 0.06))
    sksk = sk.Sketch("XY"); sksk.add(t="rect", x0=0, y0=0, x1=10, y1=5); sksk.add(t="circle", cx=5, cy=2.5, r=1)
    C.append(_caso("CAD (sketch)", "retângulo com furo: área", 50 - math.pi, sksk.area(), 1e-12))
    C.append(_caso("Fadiga", "Goodman reverso puro: n=Se/σa", 1.25, fa.safety_factors(160.0, 0.0, 200.0, 600.0, 400.0)["Goodman"], 1e-12))
    if sr.detect("CalculiX").instalado:
        from . import casos_nl as cn
        r2 = cn.barra_plastica(210000, .3, 250, 2100, 20, 4, 0.006)
        C.append({"modulo": "Estrutural (plasticidade)", "caso": "barra bilinear: |erro| < 2 %", "esperado": 0.0, "obtido": r2["erro_pct"], "tol_rel": 2.0, "ok": abs(r2["erro_pct"]) < 2.0, "estado": "ok" if abs(r2["erro_pct"]) < 2.0 else "falhou"})
    selos = {}
    for c in C: selos.setdefault(c["modulo"], []).append(c["ok"])
    out = {m: ("CONFERIDO" if all(v) else "FALHOU") for m, v in selos.items()}
    if not sr.detect("CalculiX").instalado: out["Estrutural (plasticidade)"] = "NAO_EXECUTADO"
    out["CFD"] = "NAO_EXECUTADO"
    return {"casos": C, "selos": out, "aviso": "selo = coerência com a teoria nos casos listados; NÃO é validação contra ensaio"}


if __name__ == "__main__":
    r = rodar()
    for c in r["casos"]: print(f"[{c['estado']:6}] {c['modulo']}: {c['caso']}  esperado={c['esperado']:.6g} obtido={c['obtido']:.6g}")
    print(r["selos"], "\n" + r["aviso"])
