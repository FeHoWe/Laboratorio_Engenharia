# Laboratorio_Engenharia

Repositório do **NEXUS ENGINEERING LAB**, um laboratório digital de engenharia em Python:
importa modelos CAD (STEP, STL, OBJ, FCStd), mostra em 3D, faz desmontagem virtual,
calcula propriedades e roda análises (treliça, FEA 3D, CFD com OpenFOAM, dinâmica veicular, F1).

O código fica em [`NEXUS_ENGINEERING_LAB/`](NEXUS_ENGINEERING_LAB/). O README do próprio
projeto explica como instalar e rodar no Windows.

## Versões

Cada versão é um commit no histórico, em ordem, e o conteúdo de cada commit é exatamente o do
zip daquela versão. Os links abaixo abrem ou baixam o projeto como estava em cada versão.

| Versão | Data | Destaques | Ver | Baixar |
|---|---|---|---|---|
| **V3.4** | 11/11/2026 | Estudo de malha da esfera com GCI, NEXUS INTELLIGENCE generativo opcional, guia WSL2 + OpenFOAM | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/dab507cc75ef16825dfc0c49133d93b6c5b096e1/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/dab507cc75ef16825dfc0c49133d93b6c5b096e1.zip) |
| V3.3 | 11/11/2026 | Cinco produtos (CAD, STRUCTURAL, AERODYNAMICS, VEHICLE, INTELLIGENCE); inclui a V3.2 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/fe203536656dc0646195127ca762d52496ae1f96/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/fe203536656dc0646195127ca762d52496ae1f96.zip) |
| V3.1 | 10/11/2026 | FEA em processo isolado, leitura do .frd do CalculiX, log e backup | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/afd280b4e5d5bf1b8ddb3d2ff8c177f2b7f01a5d/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/afd280b4e5d5bf1b8ddb3d2ff8c177f2b7f01a5d.zip) |
| V3.0 | 10/11/2026 | NEXUS CORE, CalculiX e OpenFOAM executados de verdade, dinâmica lateral | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/f9acf74620939a82135aaed3b7c50c98826d434b/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/f9acf74620939a82135aaed3b7c50c98826d434b.zip) |
| V2.9 | 10/11/2026 | NEXUS F1 completo, análise estilo equipe, visual realista | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/ad67ff2ed80809a1881dbe46ec11dae41ca19cff/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/ad67ff2ed80809a1881dbe46ec11dae41ca19cff.zip) |
| V2.8 | 09/11/2026 | F1 2027, F1 clássicos, aeronaves, Engenharia/Telemetria F1 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/0c3e95458436a994e05d8a5ce63dac76e2dca976/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/0c3e95458436a994e05d8a5ce63dac76e2dca976.zip) |
| V2.7 | 06/11/2026 | Sete novos projetos predefinidos (Wankel, V12, robô, turbojato…) | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/f080499294a1b797f692a65d7ead5259e288abeb/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/f080499294a1b797f692a65d7ead5259e288abeb.zip) |
| V2.6 | 06/11/2026 | Rastreabilidade, FEA 3D Tet4/Tet10, solvers, dinâmica longitudinal | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/9599b643473278c24d516e0c1ad1a85f0a82d0f8/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/9599b643473278c24d516e0c1ad1a85f0a82d0f8.zip) |
| V2.5 | 06/11/2026 | NEXUS Engineering Arsenal (biblioteca versionada de componentes) | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/66bc78bc89be874f304f3b04e8ac94b156fb139e/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/66bc78bc89be874f304f3b04e8ac94b156fb139e.zip) |
| V2.4 | 05/11/2026 | Treliça (MEF de barras), relatórios rastreáveis; inclui a V2.3 | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/347a2610ca08e27dd9efcdfd04110b1ac6223651/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/347a2610ca08e27dd9efcdfd04110b1ac6223651.zip) |
| V2.2 | 05/11/2026 | Projetos predefinidos, biblioteca de peças, laboratório de testes | [código](https://github.com/FeHoWe/Laboratorio_Engenharia/tree/152263c8a843b0a3cf061333c3e85e4958dcfba6/NEXUS_ENGINEERING_LAB) | [zip](https://github.com/FeHoWe/Laboratorio_Engenharia/archive/152263c8a843b0a3cf061333c3e85e4958dcfba6.zip) |

As V2.3 e V3.2 não tinham zip próprio. As mudanças delas já estão nas versões
seguintes (V2.4 e V3.3). O histórico completo está no `README.md` e no `CHANGELOG.md` do projeto.

## Como pegar uma versão antiga

Pelo navegador: use o link **zip** da tabela.

Pelo Git:

```
git clone https://github.com/FeHoWe/Laboratorio_Engenharia.git
cd Laboratorio_Engenharia
git log --oneline                # lista as versões (um commit por versão)
git checkout 0c3e954             # exemplo: V2.8
```

Para ver o que mudou entre duas versões: `git diff fe20353 dab507c --stat` (V3.3 → V3.4).
