# NEXUS — Estudo de malha da esfera (CFD OpenFOAM)

**Objetivo:** verificar se o pipeline CFD do NEXUS reproduz o arrasto de uma esfera lisa. **Resultado: concordância INDICATIVA, NÃO validação.**

Caso: esfera D = 1 m, V∞ = 20 m/s, ν = 2·10⁻⁴ m²/s (Re = 10⁵ por similaridade — ν não é do ar, é só para fixar o Re), ρ = 1,225, k-ω SST com funções de parede, domínio afastado do solo (folga 4 m), bloqueio 4,2 %. Área de referência = πD²/4 (área frontal real). Reprodução: `python tools/estudo_esfera.py`.

| Malha (células de fundo) | Iterações | Convergiu | Cd pressão | Cd atrito (estim.) | Cd total (estim.) | Cl (estim.) |
|---|---|---|---|---|---|---|
| grossa 40×16×16 | 500 | não | 0,458 | 0,0031 | 0,461 | +0,382 |
| média 60×24×24 | 700 | não | 0,542 | 0,0018 | 0,544 | −0,017 |
| fina 80×32×32 | 900 | **sim** | 0,505 | 0,0018 | 0,507 | −0,177 |

Referência clássica (esfera lisa, Re ≈ 10⁵, regime subcrítico): Cd ≈ 0,47 (valor tabelado em Schlichting / Hoerner — **conferir na sua fonte antes de citar**).

## Leitura honesta
- Só a malha fina convergiu; ela dá Cd ≈ 0,51, ~8 % acima de 0,47. Isso está dentro de uma tolerância de 10 %, mas **não basta** para chamar de VALIDADO.
- O Cd **não é monotônico** com o refino (0,46 → 0,54 → 0,51): não há convergência de malha demonstrada, então não se calcula GCI nem se afirma independência de malha.
- **Cl ≠ 0** (−0,18 na malha fina) numa esfera: sinal de assimetria da malha (snappyHexMesh) / escoamento ainda levemente instável. Uma esfera não deveria ter sustentação média.
- k-ω SST totalmente turbulento prevê o descolamento de forma diferente da camada limite real em Re = 10⁵ (laminar até a separação); a boa concordância pode ser parcialmente coincidência.
- O atrito é **estimativa de 1ª ordem** (lei da parede); o Cd de pressão vem do campo, por integração própria (o `forceCoeffs` do OpenFOAM v1912 deste ambiente falha por defeito do build).

## Por que o NEXUS não marca VALIDADO
`executar_openfoam` só concede VALIDADO com Cd da função-objeto **e** convergência **e** concordância com referência citada. Neste build a função-objeto não roda, logo o resultado permanece SIMULAÇÃO NUMÉRICA. Isso é intencional.

## O que faltaria para validar de fato
Malha com camadas de prisma (y⁺ controlado), estudo com ≥ 3 refinos monotônicos e GCI, malha simétrica, OpenFOAM com `forceCoeffs` funcional (ex.: v2306+/WSL2), e referência com Re e rugosidade idênticos.
