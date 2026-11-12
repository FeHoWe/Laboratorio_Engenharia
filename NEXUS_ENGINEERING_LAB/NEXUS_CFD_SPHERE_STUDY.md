# NEXUS — Estudo de malha da esfera (CFD OpenFOAM) — rev. 2 (V3.4)

**Objetivo:** verificar se o pipeline CFD do NEXUS reproduz o arrasto de uma esfera lisa.
**Resultado: concordância forte e convergência de malha demonstrada, mas NÃO marcado VALIDADO** (motivos abaixo).

Caso: esfera D = 1 m, V∞ = 20 m/s, ν = 2·10⁻⁴ m²/s (Re = 10⁵ por similaridade — ν não é do ar, só fixa o Re), ρ = 1,225, k-ω SST com funções de parede.
**Mudanças desde a rev. 1:** domínio de **ar livre e simétrico** (corpo centrado, sem solo — o solo próximo era a causa do Cl espúrio), **área de referência = área frontal projetada da malha** (πD²/4 = 0,785 m², erro de rasterização 0,13 %), 3 refinos com razão **constante 1,5**, 1500 iterações cada. Reprodução: `python tools/estudo_esfera.py` (~45 min).

| Malha (fundo) | Cd pressão | Cd atrito (estim.) | **Cd total (estim.)** | Cl | Convergiu (resíduos) |
|---|---|---|---|---|---|
| grossa 48×24×24 | 0,5010 | 0,0017 | **0,5027** | −0,006 | não |
| média 72×36×36 | 0,4793 | 0,0012 | **0,4805** | +0,004 | não |
| fina 108×54×54 | 0,4676 | 0,0020 | **0,4696** | +0,003 | não |

**GCI (Roache/Celik, 3 malhas, sequência monotônica):** ordem aparente p = 1,75; valor extrapolado Cd ≈ **0,459**; GCI da malha fina = **2,8 %**.
Referência clássica (esfera lisa, Re ≈ 10⁵ subcrítico): Cd ≈ 0,47 — **conferir na sua fonte**. A malha fina fica 0,1 % dela; o extrapolado fica 2,3 % abaixo.

## Melhorias comprovadas
- **Cl ≈ 0** (|Cl| ≤ 0,006) em todas as malhas: era −0,18 na rev. 1. Simetria do domínio resolveu.
- **Convergência monotônica** (0,503 → 0,481 → 0,470), logo GCI se aplica; antes era oscilatória (0,46 → 0,54 → 0,51).

## Por que ainda NÃO é VALIDADO (regra do NEXUS)
1. Nenhuma das malhas atingiu o critério de resíduos em 1500 iterações — os valores são de regime aproximado, não de convergência declarada.
2. O Cd total usa **atrito ESTIMADO** (lei da parede, 1ª ordem) e pressão por integração própria; a função-objeto `forceCoeffs` do OpenFOAM v1912 deste ambiente não roda (defeito do build). O NEXUS só concede VALIDADO com Cd da função-objeto.
3. k-ω SST totalmente turbulento a Re = 10⁵ não representa a camada limite laminar real até a separação; o acerto com 0,47 pode ter componente de coincidência.
4. A referência precisa ser citada por você (fonte/Re/rugosidade) para registrar `validacao_ref`.

## Próximo passo para validar de fato
OpenFOAM ≥ v2306 (WSL2, `forceCoeffs` funcional), mais iterações até o `residualControl`, e uma segunda referência (ex.: cilindro ou placa plana) para não depender de um único ponto.
