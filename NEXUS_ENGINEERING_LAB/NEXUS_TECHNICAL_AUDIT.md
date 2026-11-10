# NEXUS ENGINEERING LAB — Auditoria técnica (Fase 0)

Data: 2026-11-10 · Versão auditada: V2.9 → entregue como V3.0 · Método: leitura do código-fonte, execução da suíte de testes e execução real dos solvers externos num ambiente Linux de teste.

## 1. Arquitetura real (não presumida)
| Item | Achado |
|---|---|
| Linguagem | Python 3.13 (alvo: Windows 11; testado em Linux headless) |
| Interface | PySide6 (Qt). `interface/*` não calcula; `core/` e `modules/` não importam Qt |
| Renderização 3D | VTK (`interface/viewport.py`); visualizador móvel em three.js r128 |
| Kernel CAD | OpenCASCADE via `cadquery-ocp` (OCP). **CadQuery e FreeCAD NÃO são usados** (decisão antiga em `docs/ARQUITETURA.md`) |
| Malhador | Gmsh (módulo Python; precisa de libGLU no Linux). Voxel próprio como alternativa |
| FEA | NEXUS-Tet4 e NEXUS-Tet10 (próprios, esparsos) + exportação/execução CalculiX (`modules/calculix_io.py`) |
| CFD | `modules/cfd_case.py`: níveis analíticos 1–2 + gerador/executor de caso OpenFOAM (nível 3) |
| Dinâmica veicular | `vehicle_dynamics.py` (longitudinal RK4), `lapsim.py`, `nexus_f1/` (volta quase-estacionária, pneus, ERS) |
| Persistência | `.nexus` (ZIP: JSON + B-Rep) para montagens; `*.nexus.json` para projetos do usuário; Arsenal em SQLite (`~/.nexus_engineering_lab/arsenal.db`); materiais em `data/materials.db` |
| Código | ~23 mil linhas em `core/ modules/ interface/ samples/ nexus_f1/ mobile/`; 338+ funções de teste em `tests/` |

## 2. Dependências (diagnóstico real, ambiente de teste)
OCP 8.0 ✔ · Gmsh 4.15 ✔ · NumPy/SciPy/PySide6/VTK/trimesh/reportlab/openpyxl ✔ · meshio ✘ · pyvista ✘ · cadquery ✘ · **CalculiX 2.21: instalado no ambiente de teste durante esta fase** · **OpenFOAM v1912: instalado no ambiente de teste durante esta fase** · ParaView ✘ · WSL2 n/a (Linux). Na máquina do usuário (Windows 11) nada disso foi verificado: use *Ferramentas ▸ Solvers ▸ Diagnóstico completo*.

## 3. Cálculos existentes e sua classe
- **Analíticos:** ISA, arrasto/downforce, asa (linha sustentadora), vigas, colunas, parafusos, eixos, vasos, fadiga/Miner/mola, treliça e pórtico 3D (MEF de barras), dinâmica longitudinal RK4, volta quase-estacionária F1.
- **Numéricos próprios:** FEA 3D Tet4/Tet10 (verificados contra viga/Timoshenko e placa com furo/Peterson).
- **Animações prescritas (NÃO são simulação):** movimentos dos mecanismos (motor, F1, aeronaves) — rotuladas como `ANIMACAO_PRESCRITA`.
- **Demonstrativo/limitado:** FEA com malha de voxels (escada) não é confiável para tensão local; CFD nível 1–2 não é CFD.

## 4. Biblioteca / Arsenal
- A biblioteca paramétrica contém **18 peças** (`samples/library.py`). Textos antigos (README, vitrine do celular) diziam **19**: era contagem desatualizada, nenhuma peça foi removida pelo código; corrigido para 18. Se você tem uma 19ª peça salva no **seu** `arsenal.db`, ela é preservada: o código nunca apaga/migra o banco.
- Arsenal: SQLite, ID `NEXUS-COMP-000001`, versões major.minor, `modify` cria nova versão, `restore` cria nova versão com conteúdo antigo, `duplicate`, `compare`, `export_component`, exclusão confirmada e bloqueada se em uso por projeto.

## 5. Lacunas frente ao Master Prompt (diagnóstico) e ação
| Requisito | Estado antes | Ação nesta entrega |
|---|---|---|
| NEXUS CORE: processos isolados, fila, cancelamento, UI sem congelar | **Ausente** (cálculos síncronos) | `core/jobs.py` + `core/job_worker.py` |
| Diagnóstico de ambiente (§12) | Parcial (só Gmsh/CalculiX/OpenFOAM) | `core/doctor.py` completo + botão na interface |
| Invalidar resultados ao mudar geometria (§9) | **Ausente** | `modules/result_store.py` + `ProjectStore.refresh_results` |
| FEA Gmsh→CalculiX real | Escrito, **nunca executado** | Executado de verdade e coberto por teste (`tests/test_calculix_real.py`) |
| CFD OpenFOAM | Gerador **nunca executado**; continha defeitos | Executado de verdade; 3 defeitos corrigidos (ver §6) |
| Dinâmica veicular lateral/pneu/suspensão (§8) | Só longitudinal | `modules/vehicle_lateral.py` (+ calculadora desktop + aba celular) |
| STL: não prometer edição paramétrica | OK (importa como malha) | mantido |

## 6. Defeitos encontrados executando de verdade
1. `blockMeshDict`: patch `sides` reunia duas faces não coplanares, o que `symmetryPlane` não aceita → separado em `sideL`/`sideR`.
2. Faltava `constant/turbulenceProperties` (OpenFOAM ESI ≤ v1912) e a chave `RASModel` → gerados os dois formatos (`momentumTransport`/`model` e `turbulenceProperties`/`RASModel`).
3. `executar_openfoam` descartava Cd/Cl e convergência → agora lê log e `forceCoeffs`; não declara VALIDADO sem referência.
4. Neste build Debian do OpenFOAM v1912, **qualquer função-objeto aborta** (`IOstream "sha1"`). O NEXUS detecta, roda sem elas e usa integração própria de pressão (`forcas_pressao`), declarando que não inclui atrito viscoso.
5. Matrizes de pose do F1 2027 no celular perdiam rigidez (~0,2%) por interpolação linear → reortonormalização.

## 7. Riscos remanescentes
Interface Qt ainda chama cálculos longos de forma síncrona na maioria dos diálogos (a fila existe e é testada, mas o uso nos diálogos de FEA/CFD é a próxima fase). Sem GPU não houve teste visual da janela VTK. Nada foi testado em Windows 11 real.
