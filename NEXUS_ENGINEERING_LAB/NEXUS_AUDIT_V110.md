# Auditoria V100.0 → V110.0 (Fase A)

Base medida: suíte completa da V100.0 = 757 + 41 testes passados, 4 ignorados (ferramentas externas ausentes), 0 falhas (executada nesta sessão sobre o mesmo código).

## Método
Referências cruzadas por texto entre `modules/*.py` e (a) `interface/`, `main/`, `nexus_f1/` (GUI), (b) `nexus_cli.py`, (c) `tests/`. Referência textual NÃO prova que a função funciona na tela; é só um mapa de onde olhar.

## Módulos sem referência na GUI
- **Lacuna real (só API/CLI):** `validacao_dados`, `calibracao`, `carro_do_projeto`, `lapsim_bicicleta`, `dinamica_lateral`, `freio_termico`, `dossie`.
- **Internos, usados indiretamente (sem lacuna):** `calculix_io`, `calculix_nl`, `cfd_case`, `declared_joints`, `result_store`, `snapshot`, `units`, `sketch_solver` (via `sketch2d`).
- **A verificar na Fase D/C:** `lapsim_veiculo` (só via `veiculo_job`), `interference_sweep`, `cfd_gci` (só testes).

## Duplicidades e inconsistências encontradas
- Existem DOIS lapsim: ponto material (`lapsim`) e veículo com transferência de carga (`lapsim_veiculo`), além do `lapsim_bicicleta` (V60, sem transferência lateral). São modelos diferentes, não duplicatas, mas a GUI não deixa isso claro → Fase D: painel único com o modelo escolhido e suas hipóteses.
- `NEXUS HOME` (V5.0) já é uma tela inicial por ambientes: o “Control Center” será uma EVOLUÇÃO dela, não uma segunda tela.

## Limitações conhecidas (herdadas, não escondidas)
- Windows 11, WSL2 e instalador nunca foram executados em máquina real.
- Traduções de IA sem revisão nativa; textos novos do celular só em português.
- FEA/CFD externos (CalculiX/OpenFOAM) ausentes no sandbox: os testes correspondentes são ignorados aqui.
- Sem GUI para os módulos 30–90 (será tratado na Fase B).

## Plano
B: Control Center sobre a Home + diálogo “Estudos avançados” (validação, calibração, freios, dinâmica lateral, dossiê). C: FEA 3D no viewport + invalidação de resultados. D: Vehicle Dynamics 2.0 (painel A/B). E: F1 2.0 (estratégia/pit, setores). F: Digital Twin + AI Engineer (camada de ferramentas, sem inventar números). G: relatório técnico consolidado. H: Windows — só preparar e documentar; NÃO VALIDADO.

## Adendo — Fase E (F1 2.0): verificação sem código novo
O app `nexus_f1` JÁ implementa (com testes em `tests/test_nexus_f1*.py`): volta por circuito com setores (`laptime`, `circuits.sector_bounds`), pneus/compostos e degradação com modelo declarado (`tires`), estratégia de pit stop com perda de pit configurável — “não é dado oficial” (`strategy`), delta de tempo e deltas por segmento (`analysis`), varredura/sensibilidade/otimização (`analysis`), comparação A/B/C (`compare`), relatório de estratégia (`report`). Nada foi duplicado nesta rodada. Ficam como lacunas assumidas: gráficos sincronizados de telemetria A×B ao longo da volta na janela do estudo F1 e relatório técnico único da sessão com imagens 3D.
