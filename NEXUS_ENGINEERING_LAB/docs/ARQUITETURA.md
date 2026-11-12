# Arquitetura do NEXUS ENGINEERING LAB V1.0

## Camadas (dependências só apontam para baixo)
```
interface/   telas Qt/VTK (main_window, viewport, component_tree, properties_panel, toolbar, styles)
modules/     regras de negócio (importer, solid_analyzer, explode_engine, component_inspector,
             exporter, material_manager, selection_manager)
core/        modelo e infraestrutura (model, geometry, cad_engine, component_manager,
             assembly_manager, project_manager)
```
`interface` não calcula geometria; `core`/`modules` não conhecem Qt (por isso são testáveis sem tela).

## Decisões
- **OCP (OpenCascade via cadquery-ocp) no lugar do FreeCAD.** O FreeCAD não estava instalado e exigiria
  seu próprio Python. O OCP é o mesmo kernel do FreeCAD, instala com `pip` e funciona no Windows. Só
  `core/cad_engine.py` importa OCP: trocar o backend afeta um arquivo. FCStd é lido direto do ZIP/XML
  (não paramétrico). `main/nexus_main.FCMacro` é só um lançador e **não foi testado**.
- **Geometria em coordenadas do mundo; explosão = deslocamento por nó.** A geometria nunca é alterada;
  restaurar = zerar os deslocamentos (verificado em teste).
- **Explosão**: centro da montagem, centros das caixas dos filhos, direção radial/eixo, módulo proporcional
  à distância ao centro e à diagonal, escala por nível hierárquico, resolução iterativa de interferências.
  Nenhum valor aleatório.
- **Projeto `.nexus`**: ZIP com `project.json` + formas B-Rep (`shapes/*.bin`) + malhas (`meshes/*.npz`);
  gravação atômica (arquivo temporário + `os.replace`).
- **Arquivos além da estrutura sugerida**: `core/model.py` (dataclass Component compartilhada por todas as
  camadas), `modules/solid_analyzer.py` (separação de sólidos é regra de negócio própria),
  `tests/fixtures.py` (gera STEP/STL/OBJ/FCStd de teste).
- Unidades: mm, mm², mm³, g. Dimensões = caixa alinhada aos eixos do mundo.

## Limitações conhecidas
- Dimensões são da caixa delimitadora, não de "diâmetro/comprimento" paramétricos.
- Malhas (STL/OBJ): volume/massa só se a malha for fechada.
- Nomes de instâncias repetidas no STEP exportado perdem acentos (ASCII).
- Restrições/juntas de montagem não são lidas/gravadas.
- FCStd: só leitura, sem histórico paramétrico; testado apenas com arquivos gerados por nós, não com FreeCAD real.
- Janela 3D não foi validada em GPU real aqui (ambiente sem GPU); renderização conferida via EGL offscreen.

## Roadmap
V1.1 geometria de referência/medidas · V1.5 editor paramétrico · V2.0 física · V2.1 movimento ·
V2.2 materiais · V3.0 elementos finitos · V3.1 térmica/vibração · V4.0 Engineering Assistant.

## Notas V1.1–V1.2
- `modules/measure_engine.py`: distância (`BRepExtrema_DistShapeShape` via `CadEngine.min_distance`), diâmetros e
  ângulos a partir de faces analíticas (`CadEngine.analytic_faces`). Ângulo = entre eixos de cilindros dominantes ou
  normais das maiores faces planas; a base usada sempre é informada. Malhas não têm diâmetro/ângulo (campo indisponível).
- Corte de seção = planos de recorte do VTK nos mapeadores; a geometria não é alterada.
- Em Qt `offscreen` (testes/CI) o desenho VTK é pulado e o HUD de texto fica desligado (exige OpenGL real); o visual
  foi validado por renderização EGL fora da tela. Em Windows com GPU o HUD fica ativo.
