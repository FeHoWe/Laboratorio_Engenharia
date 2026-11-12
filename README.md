# Laboratorio_Engenharia

Repositório do **NEXUS ENGINEERING LAB**, um laboratório digital de engenharia em Python:
importa modelos CAD (STEP, STL, OBJ, FCStd), mostra em 3D, faz desmontagem virtual,
calcula propriedades e roda análises (treliça, FEA 3D, CFD com OpenFOAM, dinâmica veicular, F1).

O código fica em [`NEXUS_ENGINEERING_LAB/`](NEXUS_ENGINEERING_LAB/). O README do próprio
projeto explica como instalar e rodar no Windows.

## Versões

Cada versão é um commit no histórico do branch, marcado com uma tag (`v2.2`, `v2.4`, …).
O conteúdo de cada tag é exatamente o do zip daquela versão.

| Versão | Data | Destaques | Ver | Baixar |
|---|---|---|---|---|
| **V3.4** | 11/11/2026 | Estudo de malha da esfera com GCI, NEXUS INTELLIGENCE generativo opcional, guia WSL2 + OpenFOAM | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v3.4/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v3.4.zip) |
| V3.3 | 11/11/2026 | Cinco produtos (CAD, STRUCTURAL, AERODYNAMICS, VEHICLE, INTELLIGENCE); inclui a V3.2 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v3.3/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v3.3.zip) |
| V3.1 | 10/11/2026 | FEA em processo isolado, leitura do .frd do CalculiX, log e backup | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v3.1/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v3.1.zip) |
| V3.0 | 10/11/2026 | NEXUS CORE, CalculiX e OpenFOAM executados de verdade, dinâmica lateral | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v3.0/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v3.0.zip) |
| V2.9 | 10/11/2026 | NEXUS F1 completo, análise estilo equipe, visual realista | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.9/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.9.zip) |
| V2.8 | 09/11/2026 | F1 2027, F1 clássicos, aeronaves, Engenharia/Telemetria F1 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.8/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.8.zip) |
| V2.7 | 06/11/2026 | Sete novos projetos predefinidos (Wankel, V12, robô, turbojato…) | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.7/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.7.zip) |
| V2.6 | 06/11/2026 | Rastreabilidade, FEA 3D Tet4/Tet10, solvers, dinâmica longitudinal | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.6/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.6.zip) |
| V2.5 | 06/11/2026 | NEXUS Engineering Arsenal (biblioteca versionada de componentes) | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.5/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.5.zip) |
| V2.4 | 05/11/2026 | Treliça (MEF de barras), relatórios rastreáveis; inclui a V2.3 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.4/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.4.zip) |
| V2.2 | 05/11/2026 | Projetos predefinidos, biblioteca de peças, laboratório de testes | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/v2.2/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/refs/tags/v2.2.zip) |

As V2.3 e V3.2 não tinham zip próprio. As mudanças delas já estão nas versões
seguintes (V2.4 e V3.3). O histórico completo está no `README.md` e no `CHANGELOG.md` do projeto.

## Como pegar uma versão antiga

```
git clone https://github.com/FeHoWe/Laboratorio_Engenharia.git
cd Laboratorio_Engenharia
git checkout v2.8        # qualquer tag da tabela
```

Para comparar duas versões: `git diff v3.3 v3.4 --stat`.
