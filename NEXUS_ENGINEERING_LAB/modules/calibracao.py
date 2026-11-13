"""V40 — Calibração de parâmetros do `lapsim` contra telemetria SUA + diagnóstico de identificabilidade.

Ajusta (mínimos quadrados) os parâmetros que você liberar, dentro das faixas que você der, para reproduzir a velocidade medida.
IMPORTANTE (honestidade): os valores calibrados são valores EFETIVOS do modelo simplificado — absorvem erros de modelo, de sincronismo e de medição;
NÃO são propriedades físicas medidas. Parâmetros mal identificáveis (muito correlacionados ou na borda da faixa) são sinalizados. Incertezas vêm de
linearização em torno do ótimo, supõem resíduos independentes (otimista, pois resíduos de telemetria são autocorrelacionados) e servem só como ordem de grandeza.
`frac_treino` < 1 calibra só com o início da volta e mede o erro no restante (validação por trecho): é o teste mínimo contra “decorar” a telemetria.
"""
from __future__ import annotations

import math
from dataclasses import asdict, replace

from . import lapsim
from .validacao_dados import TelemetriaError, _interp


def _preparar(telemetria, pista, ds, base):
    r = lapsim.volta(base, pista, ds)
    s_sim = r.valores["s_m"]
    s0 = telemetria["s_m"][0]
    s_med = [x - s0 for x in telemetria["s_m"]]
    pts = [i for i, s in enumerate(s_sim) if s <= s_med[-1]]
    if len(pts) < 20:
        raise TelemetriaError("sobreposição insuficiente entre a telemetria e a pista simulada")
    vm = [_interp(s_sim[i], s_med, telemetria["v_kmh"]) for i in pts]
    return s_sim, pts, vm


def _matriz_inversa(A):
    n = len(A)
    M = [list(map(float, r)) + [1.0 if i == j else 0.0 for j in range(n)] for i, r in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-300:
            return None
        M[c], M[p] = M[p], M[c]
        d = M[c][c]
        M[c] = [x / d for x in M[c]]
        for r in range(n):
            if r != c:
                f = M[r][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [r[n:] for r in M]


def calibrar(base: lapsim.Carro, parametros: dict, telemetria: dict, pista=None, ds: float = 3.0, frac_treino: float = 1.0, max_nfev: int = 60) -> dict:
    from scipy.optimize import least_squares
    import numpy as np
    if not parametros:
        raise ValueError("informe ao menos um parâmetro a calibrar")
    ok = set(asdict(base))
    for k, (lo, hi) in parametros.items():
        if k not in ok:
            raise ValueError(f"parâmetro desconhecido: {k}")
        if not lo < hi:
            raise ValueError(f"faixa inválida para {k}")
        if not lo <= getattr(base, k) <= hi:
            raise ValueError(f"o valor inicial de {k} ({getattr(base, k):g}) está fora da faixa [{lo:g}, {hi:g}]")
    if not 0.2 <= frac_treino <= 1.0:
        raise ValueError("frac_treino deve estar entre 0,2 e 1")
    nomes = list(parametros)
    lo = np.array([parametros[k][0] for k in nomes], float)
    hi = np.array([parametros[k][1] for k in nomes], float)
    s_sim, pts, vm = _preparar(telemetria, pista, ds, base)
    corte = max(10, int(len(pts) * frac_treino))
    tr, te = list(range(corte)), list(range(corte, len(pts)))

    def carro(u):
        x = lo + np.asarray(u) * (hi - lo)
        return replace(base, **{k: float(v) for k, v in zip(nomes, x)})

    def vel(c):
        r = lapsim.volta(c, pista, ds).valores["v_ms"]
        return [r[i] * 3.6 for i in pts]

    def res(u, idx=tr):
        v = vel(carro(u))
        return np.array([v[i] - vm[i] for i in idx])

    u0 = (np.array([getattr(base, k) for k in nomes], float) - lo) / (hi - lo)
    r0 = res(u0)
    sol = least_squares(res, u0, bounds=(0.0, 1.0), max_nfev=max_nfev, diff_step=1e-4, x_scale=1.0)
    u = sol.x
    rms = lambda e: float(math.sqrt(float(np.mean(np.square(e)))))  # noqa: E731
    antes_tr, depois_tr = rms(r0), rms(res(u))
    teste = None
    if te:
        teste = {"rmse_antes_kmh": rms(res(u0, te)), "rmse_depois_kmh": rms(res(u, te)), "n_pontos": len(te)}
    # identificabilidade: Jacobiano por diferenças centrais no ótimo, em coordenadas normalizadas (0–1)
    J = np.zeros((len(tr), len(nomes)))
    for j in range(len(nomes)):
        h = 1e-3
        up, um = u.copy(), u.copy()
        up[j] = min(1.0, u[j] + h); um[j] = max(0.0, u[j] - h)
        J[:, j] = (res(up) - res(um)) / (up[j] - um[j])
    sv = np.linalg.svd(J, compute_uv=False)
    cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf")
    sigma2 = float(np.sum(np.square(res(u)))) / max(1, len(tr) - len(nomes))
    cov = _matriz_inversa((J.T @ J).tolist())
    corr, incert = [], {}
    avisos = []
    if cov is not None and all(cov[i][i] > 0 for i in range(len(nomes))):
        for i in range(len(nomes)):
            incert[nomes[i]] = math.sqrt(sigma2 * cov[i][i]) * (hi[i] - lo[i])
            for j in range(i + 1, len(nomes)):
                c = cov[i][j] / math.sqrt(cov[i][i] * cov[j][j])
                corr.append({"par": [nomes[i], nomes[j]], "correlacao": float(c)})
                if abs(c) > 0.95:
                    avisos.append(f"{nomes[i]} e {nomes[j]} estão muito correlacionados ({c:+.3f}): a telemetria não os separa — o ajuste pode trocar um pelo outro.")
    else:
        avisos.append("Matriz de informação singular: pelo menos um parâmetro não afeta a velocidade medida (ou há dependência exata); incertezas indisponíveis.")
    na_borda = [k for k, x in zip(nomes, u) if x < 1e-3 or x > 1 - 1e-3]
    if na_borda:
        avisos.append("Na borda da faixa: " + ", ".join(na_borda) + " — o ótimo pode estar fora da faixa informada ou o modelo compensa outro erro.")
    if cond > 1e4:
        avisos.append(f"Número de condição alto ({cond:.1e}): parâmetros mal identificáveis com esta telemetria.")
    if teste and teste["rmse_depois_kmh"] > 1.5 * max(depois_tr, 1e-9) and teste["rmse_depois_kmh"] > teste["rmse_antes_kmh"] * 0.8:
        avisos.append("O erro no trecho NÃO usado na calibração melhorou pouco ou piorou: possível ajuste de ruído/sobreajuste ou modelo insuficiente.")
    if depois_tr > 0.8 * antes_tr and antes_tr > 1e-9:
        avisos.append("A calibração reduziu pouco o erro: os parâmetros liberados não explicam a diferença (limitação do modelo).")
    valores = {k: float(lo[i] + u[i] * (hi[i] - lo[i])) for i, k in enumerate(nomes)}
    t_cal = float(lapsim.volta(carro(u), pista, ds).valores["tempo_s"])
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS-LapSim 1.0 + scipy.least_squares", "parametros_calibrados": valores,
            "valores_iniciais": {k: getattr(base, k) for k in nomes}, "carro_calibrado": asdict(carro(u)), "treino": {"rmse_antes_kmh": antes_tr, "rmse_depois_kmh": depois_tr, "n_pontos": len(tr)},
            "teste": teste, "frac_treino": frac_treino, "incerteza_aprox": incert, "correlacoes": corr, "numero_condicao": cond, "valores_singulares": [float(x) for x in sv],
            "tempo_calibrado_s": t_cal, "avaliacoes": int(sol.nfev), "convergiu": bool(sol.success), "avisos": avisos,
            "limitacoes": ["Valores EFETIVOS do modelo simplificado: absorvem erros de modelo/medição/sincronismo; não são propriedades físicas medidas.",
                           "Incerteza aproximada (linearização, resíduos independentes — otimista).",
                           "Calibrar NÃO equivale a validar: valide em outra volta com `validar`."]}


def texto(r: dict) -> str:
    L = [f"Calibração — {r['classe']} ({r['solver']}) · convergiu: {'sim' if r['convergiu'] else 'NÃO'} · {r['avaliacoes']} avaliações",
         f"  treino ({r['treino']['n_pontos']} pts): RMSE {r['treino']['rmse_antes_kmh']:.2f} → {r['treino']['rmse_depois_kmh']:.2f} km/h"]
    if r["teste"]:
        L.append(f"  trecho não usado ({r['teste']['n_pontos']} pts): RMSE {r['teste']['rmse_antes_kmh']:.2f} → {r['teste']['rmse_depois_kmh']:.2f} km/h")
    for k, v in r["parametros_calibrados"].items():
        u = r["incerteza_aprox"].get(k)
        L.append(f"  {k}: {r['valores_iniciais'][k]:.5g} → {v:.5g}" + (f"  (± {u:.2g} aprox.)" if u is not None else ""))
    L.append(f"  número de condição {r['numero_condicao']:.1e}")
    L += ["⚠ " + x for x in r["avisos"] + r["limitacoes"]]
    return "\n".join(L)
