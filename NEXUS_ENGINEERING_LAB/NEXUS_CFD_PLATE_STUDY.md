# Estudo CFD — placa plana (verificação do atrito viscoso estimado) — V3.5

Objetivo: checar `cfd_case.forcas_viscosas` contra a solução de referência da placa plana turbulenta (Schlichting: Cf = 0,455/(log10 Re_L)^2,58).
Caso: L = 1 m, largura 0,5 m, espessura 0,01 m, V = 20 m/s, ν = 1,5e-5 → Re_L ≈ 1,33e6; Cf ≈ 0,004239; alvo Cd_atrito (2 faces) = 2·Cf = 0,008478.
Executado com OpenFOAM ESI v1912 real (`tools/estudo_placa.py`). Parede por função de parede; y+ mediano da malha média ≈ 145 (faixa de função de parede, 30–300).

| Malha | Células | Convergiu (resíduos) | Cd_atrito estimado | Alvo 2·Cf | Razão |
|---|---|---|---|---|---|
| média | 80×32×32 | sim | 0,00246 | 0,00848 | 29 % |
| fina | 120×48×48 | **não** | 0,00340 | 0,00848 | 40 % |

## Conclusão (honesta)
- O estimador de atrito **subestima fortemente** o valor de referência (29 % → 40 % do alvo) e a tendência com o refino é de aproximação lenta, não de convergência. **Não está validado.**
- Possíveis causas, NÃO confirmadas: placa de espessura finita (arestas, pressão), domínio/entrada curtos para desenvolver a camada limite, função de parede sobre malha sem prismas, e a estimativa de 1ª ordem (τ = ρ(ν+νt)·Ut/y). Os function objects `forces/wallShearStress` do OpenFOAM v1912 falham neste ambiente (bug sha1), então não há comparação com o cálculo do próprio solver.
- Consequência para o produto: o Cd total do NEXUS continua rotulado **ESTIMADO**; a classe VALIDADO não é concedida. Para casos dominados por atrito, use o resultado só qualitativamente.
- Próximos passos: camadas prismáticas (addLayers), critério de convergência por resíduo, `wallShearStress` em OpenFOAM instalado sem o bug, e repetir este estudo.
