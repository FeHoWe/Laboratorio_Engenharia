# NEXUS F1 Performance Simulator

Simulador de desempenho de um carro de Fórmula 1: configura o carro, escolhe circuito e pneus, **calcula** o tempo de volta por um modelo físico (nada de tempos fixos), mostra telemetria, compara configurações/estratégias e reproduz o som do motor gerado proceduralmente.

## Instalar e rodar (Windows, Python 3.12+)

```
pip install -r requirements.txt
python main.py            # interface desktop (PySide6)
python cli.py all         # tempo em todos os circuitos
python -m pytest tests    # 52 testes
```

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `nexus_f1/core/regulations.py`, `data/seasons/*.json` | temporadas independentes; cada parâmetro tem `status` (`regulation_reference` / `estimate` / `unconfirmed`) e `src`; modo regulamentar x experimental; `create_season` nunca sobrescreve |
| `core/circuits.py` | 15 circuitos configuráveis (`register_circuit`), traçado em coordenadas e segmentos (retas/curvas com raio), fechado em loop |
| `core/tires.py` | compostos, janela térmica, desgaste/degradação, pista molhada |
| `core/laptime.py` | simulador quase-estático: passes regressivo (frenagem) + progressivo (tração) |
| `core/strategy.py`, `compare.py`, `report.py` | stints, pit stop (parâmetro), A/B/C, CSV/JSON/Markdown |
| `engine_audio/` | **módulo independente** de áudio: `RealtimeEngineSynth` (tempo real) e `SimulationAudio` (sincronizado à volta, Doppler exato) |
| `ui/` | GUI PySide6 (tema HUD) |
| `mobile/export.py` | visualizador **mobile somente leitura** (HTML autocontido) |

## O que o modelo calcula

- **Forças:** arrasto ½ρ·CdA·v², rolamento, downforce ½ρ·ClA·v², tração limitada por potência (curva de potência por rpm × marcha, ρ por altitude/temperatura) e pela aderência do eixo traseiro (círculo de atrito).
- **Curvas:** velocidade máxima por bissecção a partir de raio, downforce, μ(carga, temperatura, desgaste, umidade) com transferência lateral de carga e o eixo mais fraco limitando.
- **Frenagem:** aderência dos dois eixos com balanço de freio e capacidade do sistema; passe regressivo garante que nunca se chegue a uma curva rápido demais.
- **ERS:** entrega limitada pela energia realmente recuperada em frenagem (+MGU-H em 2025) e pelos tetos regulamentares.
- **Pneus:** temperatura por dinâmica de 1ª ordem a partir dos carregamentos; desgaste e queda de aderência (com "cliff") realimentam o tempo de volta.
- **DRS/aero ativa:** redução de arrasto/downforce nas retas elegíveis.

## Limites que você precisa conhecer

1. **Regulamento:** valores marcados `regulation_reference` foram registrados do conhecimento do autor e **precisam ser conferidos no PDF oficial da FIA**; `estimate` são parâmetros do simulador, não dados oficiais; `unconfirmed` não é aplicado (ex.: combustível 2026).
2. **Circuitos:** comprimentos/nº de curvas são os publicados; a **geometria é esquemática estimada** (fechada para bater o comprimento). Sem elevação (gradiente 0). Para usar traçados reais: `Track.from_xy(...)`.
3. **Calibração:** um único fator global de aderência (`GRIP_SCALE`) foi ajustado para os tempos ficarem, em média, próximos de tempos de classificação conhecidos (dispersão ≈ ±5%). Tempos absolutos são **indicativos**; comparações relativas (aero, pneu, massa, estratégia) são o uso mais confiável.
4. **Vídeos de referência:** não foram acessíveis na geração deste projeto; o áudio é sintetizado por parâmetros físicos gerais (firing frequency = rpm/60·cil/2, harmônicos, Doppler, absorção do ar), **sem** análise dos vídeos.
5. **Áudio local:** `QtMultimedia`/`sounddevice` quando há saída de áudio; sempre dá para exportar WAV.
