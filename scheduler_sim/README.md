# Simulador de Escalonamento (Projeto A)

> **Status:** estável para FIFO (FCFS), SRTF e PRIOp (prioridade preemptivo).  
> **Observação:** o modo **PRIOd (aging)** está documentado e executa, mas ainda estamos ajustando detalhes finos de desempates/tempo de aging para reproduzir _exatamente_ os gráficos do capítulo — ver seção “Notas sobre PRIOd (aging)”.

---

## Requisitos

- Python **3.10+**
- Sem dependências externas para a simulação e geração do **Gantt SVG** (ASCII e SVG implementados na própria base).
- Ambiente Linux/macOS/Windows (testado nas três plataformas).

Opcional para empacotamento:

- **PyInstaller** (ou **Nuitka**), caso queira gerar binários standalone.

---

## Estrutura (resumo)

```
scheduler_sim/
  cli.py                       # CLI (run/compare/step)
  data/
    caso.txt                   # exemplo simples
    mazziero_tabela6_1.txt     # dataset do capítulo 6 (Mazziero)
    aging_demo.txt             # cenário para demonstrar aging
  scheduler/
    core.py                    # engine de simulação
    algorithms/
      fifo.py                  # FIFO (FCFS) estável
      srtf.py                  # SRTF preemptivo
      priop.py                 # Prioridade preemptivo (+ aging opcional)
    io/config_parser.py        # parser do formato exigido
    viz/ascii.py               # Gantt ASCII
    viz/svg.py                 # Gantt SVG (com legenda e marcadores)
  tests/
    tests_unittest.py          # testes com unittest (stdlib)
docs/
  latex/secoes/                # saída LaTeX (gerada com --report-latex)
```

---

## Formato do arquivo de configuração

Primeira linha: `algoritmo;quantum`  
Demais linhas: `id;cor;ingresso;duracao;prioridade;lista_eventos`

```text
algoritmo_escalonamento;quantum
id;cor;ingresso;duracao;prioridade;lista_eventos
P1;#ff0000;0;8;2;
P2;#00ff00;1;4;1;
P3;#0000ff;2;9;3;
```

Notas:

- Se **cor** ou **prioridade** estiverem vazias, são definidos valores padrão (cor derivada deterministicamente do `pid`; prioridade padrão = 1).
- `lista_eventos` é mantida apenas por compatibilidade no Projeto A (não executada).
- Você pode **sobrescrever o algoritmo via CLI** (se sua versão do CLI tiver `--algo`, v. abaixo).

---

## Como executar (comandos principais)

> **Dica rápida:** sempre rode **a partir do diretório pai** da pasta `scheduler_sim/`.

### 1) Execução FULL (uma simulação, roda até o fim)

Opção A — honrar o cabeçalho do arquivo (`algoritmo;quantum`):

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/caso.txt   --mode full   --outdir out
```

Opção B — **sobrescrever o algoritmo** (se o seu `cli.py` já tem `--algo`):

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/caso.txt   --algo FIFO   --mode full   --outdir out
```

### 2) Execução STEP (por tick), com snapshots e Gantt ASCII

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/caso.txt   --mode step   --outdir out_step
```

- O terminal pedirá **Enter** para avançar 1 tick.
- Saídas adicionais no modo step: `out_step/trace.json` (snapshot de cada tick).

### 3) Comparar algoritmos (rodadas independentes + LaTeX opcional)

```bash
python3 -m scheduler_sim.cli compare   --config scheduler_sim/data/caso.txt   --algos FIFO,SRTF,PRIOP   --outdir out_compare   --tiebreaker arrival,pid   --aging-step 0
```

> **Boas práticas de tiebreaker:**
>
> - **FIFO:** `arrival,pid` (sempre).
> - **SRTF / PRIOp:** `arrival,pid` é suficiente; se usar `priority` no desempate, ele deve refletir a prioridade **efetiva** quando aging estiver ligado.
> - O `compare` permite um `--tiebreaker` global; em versões mais novas do CLI, aplicamos defaults por algoritmo.

---

## Saídas geradas

- `gantt.svg` — diagrama de Gantt (com legenda e marcadores: **ARRIVAL**, **PREEMPT**, **FINISH**).
- `summary.json` / `summary.csv` — métricas por processo (arrival, start, finish, waiting, turnaround, response, preemptions).
- `events.csv` — linha do tempo de eventos (`t`, `kind`, `pid`, `extra`).
- `trace.json` (apenas no **step**) — snapshots de estado a cada tick.

### Legenda do Gantt SVG

- **Chegada (ARRIVAL):** triângulo para baixo.
- **Preempção (PREEMPT):** linha vertical na cor configurada.
- **Término (FINISH):** losango.
- Constantes de **cores** e **dimensões** configuráveis no topo de `viz/svg.py`.

---

## Casos do livro (Cap. 6 — Mazziero)

> Arquivo: `scheduler_sim/data/mazziero_tabela6_1.txt` (quantum conforme o caso).

### FCFS (FIFO)

```bash
# Usa o cabeçalho do arquivo ou força FIFO com --algo
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/mazziero_tabela6_1.txt   --algo FIFO   --mode full --outdir out_fcfs   --tiebreaker arrival,pid
```

**Esperado:** ordem `t1:0–5, t2:5–7, t3:7–11, t4:11–12, t5:12–14` e médias próximas a **waiting=5.2**, **turnaround=8.0**.

### SRTF

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/mazziero_tabela6_1.txt   --algo SRTF   --mode full --outdir out_srtf   --tiebreaker arrival,pid
```

### PRIOp (prioridade preemptivo, **sem** aging)

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/mazziero_tabela6_1.txt   --algo PRIOP   --mode full --outdir out_priop   --tiebreaker priority,arrival,pid   --aging-step 0
```

- Este modo já bate com os gráficos/resultados do capítulo.

### PRIOd (prioridade preemptivo **com aging**)

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/mazziero_tabela6_1.txt   --algo PRIOP   --mode full --outdir out_priod   --tiebreaker priority,arrival,pid   --aging-step 1
```

> **Notas sobre PRIOd (aging):**
>
> - O aging é aplicado com base no tempo **em ready** desde o último enfileiramento.
> - Empates devem considerar **prioridade efetiva** (não só a base).
> - Estamos finalizando um ajuste fino para reproduzir _exatamente_ o gráfico do capítulo para PRIOd em todos os empates possíveis. Os demais modos já estão **OK**.

---

## Cenário de demonstração de aging

**Sem aging (baseline):**

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/aging_demo.txt   --mode full   --outdir out_aging0   --tiebreaker arrival,pid   --aging-step 0
```

**Com aging (ex.: 2 ticks):**

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/aging_demo.txt   --mode full   --outdir out_aging2   --tiebreaker arrival,pid   --aging-step 2
```

Compare `out_aging0/summary.csv` vs `out_aging2/summary.csv`: espera/turnaround dos de baixa prioridade tendem a cair; também há menos “picote” de preempções.

---

## Testes automatizados (stdlib)

Sem `pytest`, usando apenas `unittest` da biblioteca padrão:

```bash
python3 -m unittest discover -s scheduler_sim/tests -p "tests_unittest.py" -v
```

- Cobre casos essenciais de FCFS, SRTF e PRIOp.
- Sugerimos adicionar casos focados em aging assim que fixarmos a política final de PRIOd.

---

## Geração de LaTeX (relatório)

Ao final de uma execução `run`, gere/atualize uma seção LaTeX com as métrricas:

```bash
python3 -m scheduler_sim.cli run   --config scheduler_sim/data/caso.txt   --mode full --outdir out   --report-latex
```

Saída: `docs/latex/secoes/07-resultados.tex` (para compilar depois com `pdflatex` no seu projeto de relatório).

Para **comparar** e já gerar LaTeX com múltiplos algoritmos:

```bash
python3 -m scheduler_sim.cli compare   --config scheduler_sim/data/caso.txt   --algos FIFO,SRTF,PRIOP   --outdir out_compare   --tiebreaker arrival,pid   --aging-step 0
```

---

## Empacotamento multiplataforma (opcional)

### PyInstaller (simples e recomendado)

Instale **apenas** na máquina de desenvolvimento:

```bash
pip install pyinstaller
```

Gerar binário único (Linux/macOS):

```bash
pyinstaller -F -n scheduler-sim   --add-data "scheduler_sim/data:scheduler_sim/data"   -m scheduler_sim.cli
```

Windows (PowerShell/CMD):

```powershell
pyinstaller -F -n scheduler-sim ^
  --add-data "scheduler_sim\data;scheduler_sim/data" ^
  -m scheduler_sim.cli
```

Saída:

- Linux/macOS: `dist/scheduler-sim`
- Windows: `dist/scheduler-sim.exe`

Uso (sem Python instalado):

```bash
./scheduler-sim run --config scheduler_sim/data/caso.txt --mode full --outdir out
```

> **Nuitka** também funciona e costuma entregar binários mais eficientes; contudo o setup é mais detalhado. Para a disciplina, **PyInstaller** costuma ser suficiente.

---

## Dicas & Solução de problemas

- **Resultado do `run` não bate com o `compare`:**  
  Verifique se está usando `--algo` no `run` quando o cabeçalho do arquivo não coincide com o algoritmo desejado.  
  No `compare`, os algoritmos são informados explicitamente; no `run`, por padrão, usa-se o cabeçalho `algoritmo;quantum` do arquivo (a não ser que você passe `--algo`).

- **FIFO no compare diferente do run:**  
  Use `--tiebreaker arrival,pid` para FIFO. Em versões atuais, o FIFO é estável por construção (fila real ou sequência de enfileiramento), então mesmo um tiebreaker global acidental não deve mais afetar o FCFS.

- **PRIOp correto, PRIOd “estranho”:**  
  PRIOp (aging desligado) já está conforme o capítulo. Para PRIOd, confira se seu `priop.py` usa prioridade **efetiva** nos empates quando `aging_step>0` e se **não** há preempção em **empate** de prioridade efetiva. Estamos consolidando isso; veja as “Notas sobre PRIOd” acima.

---

## Licença

Projeto acadêmico para a disciplina de Sistemas Operacionais. Uso educativo.
