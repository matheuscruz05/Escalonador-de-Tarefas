
from typing import List, Optional
from ..core import TCB

def _time_header_two_rows(max_t: int, pad_len: int) -> str:
    """
    Gera cabeçalho de tempo em duas linhas (dezenas e unidades).
    
    Args:
        max_t: Tick máximo a ser representado
        pad_len: Comprimento do padding para alinhamento
    
    Returns:
        Duas linhas de string formatadas:
        Linha 1: dígitos das dezenas posicionados a cada 10 ticks
        Linha 2: dígitos das unidades para cada tick
    """
    # linha de "dezenas": coloca o dígito das dezenas no início de cada bloco de 10
    tens = [" "] * (max_t + 1)
    for i in range(0, max_t + 1, 10):
        d = (i // 10) % 10
        tens[i] = str(d)
    tens_line = "".join(tens)
    # linha de "unidades": 0..9 repetido
    ones = [str(i % 10) for i in range(max_t + 1)]
    ones_line = "".join(ones)
    # padding à esquerda para alinhar com "    PID | "
    #pad = "       "
    pad = " " * pad_len  # largura idêntica ao prefixo das linhas (4 + label_w + 3)
    return pad + tens_line + "\n" + pad + ones_line

def gantt_ascii(
    tasks: List[TCB],
    current_t: Optional[int] = None,
    horizon: Optional[int] = None,
    running: Optional[TCB] = None,
) -> str:
    """
    Retorna diagrama Gantt em formato ASCII com cabeçalho de tempo.
    
    Args:
        tasks: Lista de tarefas a serem plotadas
        current_t: Tick atual (para modo passo, trunca visualização)
        horizon: Horizonte total (garante escala mínima)
        running: Tarefa em execução (para mostrar segmento parcial)
    
    Returns:
        String formatada com gráfico ASCII multi-linha
    """
    # 1) descobre tempo máximo a partir dos segmentos
    max_seg = 0
    for t in tasks:
        for a, b in t.segments:
            if b is not None:
                max_seg = max(max_seg, b)
    # 2) decide extensão do eixo (considera horizonte, corrente e segmentos)
    max_t = max(
        horizon if horizon is not None else 0,
        current_t if current_t is not None else 0,
        max_seg,
    )
    # 3) cabeçalho em duas linhas
    # largura fixa para os rótulos (PID) e prefixo comum
    label_w = max((len(t.pid) for t in tasks), default=2)
    prefix_len = 4 + label_w + 3   # "    " + f"{pid:<{label_w}}" + " | "

    # 3) cabeçalho em duas linhas (usando o mesmo padding das linhas)
    out = [_time_header_two_rows(max_t, pad_len=prefix_len)]
    # 4) linhas das tarefas
    for t in sorted(tasks, key=lambda x: x.pid):
        #row = [f"    {t.pid} | "]
        row = [f"    {t.pid:<{label_w}} | "]
        line = [" "] * (max_t + 1)
        for a, b in t.segments:
            # Apenas desenhar segmentos que existiram até o current_t (se fornecido)
            if current_t is not None and b > current_t:
                b = current_t  # Truncar segmento no current_t
            if a < b:  # Apenas desenhar se houver algo para desenhar
                for k in range(a, b):
                    if 0 <= k <= max_t:
                        line[k] = "█"
        # desenha o trecho em execução (parcial) se houver
        if running is not None and t is running:
            if getattr(t, "last_started_at", None) is not None and current_t is not None:
                a = t.last_started_at
                b = current_t
                for k in range(a, b):
                    if 0 <= k <= max_t:
                        line[k] = "█"
        row.append("".join(line))
        out.append("".join(row))
    return "\n".join(out)
