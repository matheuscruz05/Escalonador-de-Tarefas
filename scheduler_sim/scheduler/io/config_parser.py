"""
Parser para o arquivo de configuração no formato texto simples requerido:

Linha 1: algoritmo_escalonamento;quantum
Linha 2+: id;cor;ingresso;duracao;prioridade;lista_eventos

- Padrões: quantum=2, prioridade=1. 
- Cores serão geradas automaticamente se o parâmetro não for fornecido.
- Validações: ingresso >= 0, duracao > 0.
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class TaskConfig:
    pid: str
    color: str
    arrival: int
    duration: int
    priority: int = 1
    events: str = ""

@dataclass
class SimulationConfig:
    algorithm: str
    quantum: int = 2
    tasks: List[TaskConfig] = field(default_factory=list)

def _parse_int(name: str, value: str, line_no: int | None = None) -> int:
    try:
        return int(value.strip())
    except Exception as e:
        where = f" (linha {line_no})" if line_no is not None else ""
        raise ValueError(f"Valor inválido para {name}{where}: {value!r}. Esperado inteiro.") from e

def parse_config_text(text: str) -> SimulationConfig:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("Config must have at least two lines (system line + one task line).")
    # Primeira linha
    parts = [p.strip() for p in lines[0].split(";")]
    if len(parts) < 1:
        raise ValueError("First line must include algoritmo_escalonamento[;quantum].")
    algorithm = parts[0].upper()
    quantum = _parse_int("quantum", parts[1]) if len(parts) > 1 and parts[1] else 2
    if quantum <= 0:
        raise ValueError("quantum must be > 0")
    tasks = []
    for i, ln in enumerate(lines[1:], start=2):
        cols = [c.strip() for c in ln.split(";")]
        while len(cols) < 6:
            cols.append("")
        pid, color, ingresso, duracao, prioridade, lista_eventos = cols[:6]
        if not pid:
            raise ValueError(f"Line {i}: pid must not be empty")
        # cor automática
        if not color:
            # cor determinística a partir do hash PID
            h = abs(hash(pid)) % 0xFFFFFF
            color = f"#{h:06x}"
        arrival = _parse_int("ingresso", ingresso, i)
        duration = _parse_int("duracao", duracao, i)
        if arrival < 0:
            raise ValueError(f"Line {i}: ingresso must be >= 0")
        if duration <= 0:
            raise ValueError(f"Line {i}: duracao must be > 0")
        priority = _parse_int("prioridade", prioridade, i) if prioridade else 1
        tasks.append(TaskConfig(pid=pid, color=color, arrival=arrival, duration=duration, priority=priority, events=lista_eventos))
    return SimulationConfig(algorithm=algorithm, quantum=quantum, tasks=tasks)
