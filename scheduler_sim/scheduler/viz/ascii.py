
from typing import List, Optional
from ..core import TCB

# def gantt_ascii(tasks: List[TCB], width_scale: int = 1) -> str:
#     """
#     Render a simple ASCII Gantt per task line.
#     Each segment is drawn with '█' repeated (end - start) * width_scale.
#     Idle intervals are left as spaces.
#     """
#     # Determine max time
#     max_t = 0
#     for t in tasks:
#         for (a, b) in t.segments:
#             max_t = max(max_t, b)
#     lines = []
#     for t in sorted(tasks, key=lambda x: x.pid):
#         row = [" "] * (max_t * width_scale)
#         for (a, b) in t.segments:
#             for pos in range(a * width_scale, b * width_scale):
#                 if 0 <= pos < len(row):
#                     row[pos] = "█"
#         lines.append(f"{t.pid:>6} | {''.join(row)}")
#     axis = "       " + "".join(str(i % 10) for i in range(max_t * width_scale))
#     return axis + "\n" + "\n".join(lines)

#def _time_header_two_rows(max_t: int) -> str:
def _time_header_two_rows(max_t: int, pad_len: int) -> str:
    """
    Retorna duas linhas:
      - linha 1: marca dezenas (0,1,2,...) alinhadas nas colunas múltiplas de 10
      - linha 2: dígitos das unidades 0..9
    Cada coluna = 1 tick.
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

#def gantt_ascii(tasks: List[TCB], current_t: Optional[int] = None) -> str:
def gantt_ascii(
    tasks: List[TCB],
    current_t: Optional[int] = None,
    horizon: Optional[int] = None,
    running: Optional[TCB] = None,
) -> str:
    """
    Gantt ASCII com cabeçalho de tempo em duas linhas (dezenas/unidades).
    Se 'current_t' for informado, usa-o como limite (útil no modo STEP).
    Se 'horizon' for informado, garante a escala total desde o início.
    Se 'running' for informado, desenha o segmento parcial [last_started_at, current_t).
    """
    # 1) descobre tempo máximo a partir dos segmentos
    max_seg = 0
    for t in tasks:
        for a, b in t.segments:
            if b is not None:
                max_seg = max(max_seg, b)
    # 2) decide extensão do eixo
    #max_t = max(current_t if current_t is not None else 0, max_seg)
    # 2) decide extensão do eixo (considera horizonte, corrente e segmentos)
    max_t = max(
        horizon if horizon is not None else 0,
        current_t if current_t is not None else 0,
        max_seg,
    )
    # 3) cabeçalho em duas linhas
    #out = [_time_header_two_rows(max_t)]
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
