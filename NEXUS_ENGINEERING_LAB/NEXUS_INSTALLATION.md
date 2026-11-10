# NEXUS — Instalação (Windows 11) e verificação

## Núcleo (obrigatório)
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main\main.py            (ou run_nexus.bat)
```
Verifique: *Ferramentas ▸ Solvers…▸ Diagnóstico completo* (ou `python -m core.doctor`). O diagnóstico é somente leitura.

## Motores opcionais (cada um só é usado se o diagnóstico mostrar PRONTO)
| Motor | Como instalar | Observações |
|---|---|---|
| Gmsh | `pip install gmsh` | No Linux também `libglu1-mesa`. Sem ele, use a malha voxel (menos precisa) |
| CalculiX | binários do projeto CalculiX no PATH (`ccx`) | Linux: `apt install calculix-ccx`. Testado: 2.21 |
| OpenFOAM | WSL2 + OpenFOAM (ou Docker) | Windows: PowerShell **como administrador, por sua conta**: `wsl --install`; instale Ubuntu e OpenFOAM nele. O NEXUS chama via `wsl`. Testado: ESI v1912 (pacote Debian/Ubuntu) |
| ParaView | instalador do paraview.org, `pvpython` no PATH | Só para inspeção externa; o NEXUS não depende dele |
| meshio / pyvista | `pip install meshio pyvista` | Ainda não usados pelo NEXUS (VTK próprio faz a visualização) |

O NEXUS **não instala nada sozinho** e não executa comandos administrativos. Sem o motor, a função retorna **NÃO EXECUTADO** sem números.

## Execução dos testes
```
set PYTHONPATH=%CD%
python -m pytest tests -q
```
Testes de motores externos pulam sozinhos se o motor não existir (`tests/test_calculix_real.py`, execução real do OpenFOAM em `tests/test_cfd_case.py`).

## Versão de celular
`python mobile\build_mobile_app.py <pasta_saida> <chaves dos projetos…>` (leva ~17 min com todos os projetos por causa da checagem de interferência exata) e `python mobile\validate_lab.py` (paridade JS × Python).
