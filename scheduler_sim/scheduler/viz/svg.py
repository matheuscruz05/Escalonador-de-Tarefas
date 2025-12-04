from typing import List, Tuple, Optional
from ..core import TCB

# ==== CONFIG VISUAL ====
COLOR_BG            = "#ffffff"
COLOR_CANVAS_BORDER = "#111111"
COLOR_GRID_MINOR    = "#e9e9e9"
COLOR_AXIS          = "#000000"
COLOR_BAR_BORDER    = "#333333"

COLOR_ARRIVAL       = "#1f78b4"   # triângulo (chegada)
COLOR_PREEMPT       = "#760eff"   # linha (preempção)
COLOR_FINISH        = "#000000"   # losango (término)

COLOR_IO_START      = "#ff7f00"   # círculo preenchido (início de E/S)
COLOR_IO_END        = "#33a02c"   # círculo preenchido (fim de E/S)

COLOR_MUTEX_LOCK    = "#6a3d9a"   # quadrado (lock)
COLOR_MUTEX_UNLOCK  = "#cab2d6"   # quadrado (unlock)
COLOR_MUTEX_BLOCK   = "#e31a1c"   # X (bloqueio)
COLOR_MUTEX_WAKE    = "#1b9e77"   # triângulo apontando para cima (wake)

LEGEND_BG_HEX       = "#ffffff"
LEGEND_BORDER_HEX   = "#555555"

def _task_time_horizon(tasks: List[TCB]) -> int:
    max_t = 0
    for t in tasks:
        for (s, e) in t.segments:
            if e > max_t:
                max_t = e
    return max_t


def gantt_svg(
    tasks: List[TCB],
    events: List[Tuple[int, str, str, dict]],
    svg_scale: int = 24,
    current_t: Optional[int] = None,
    horizon: Optional[int] = None,
    running: Optional[TCB] = None,
) -> str:
    """
    Gera um gráfico de Gantt em SVG.

    - `tasks`: lista de TCBs (usa `segments`, `pid`, `color`).
    - `events`: lista de tuplas (t, kind, pid, extra). Reconhece:
        ARRIVAL, PREEMPT, FINISH,
        IO_START, IO_END,
        MUTEX_LOCK, MUTEX_UNLOCK, MUTEX_BLOCK, MUTEX_WAKE.
    - `current_t` pode ser usado para modo "live" (linha vertical de tempo).
    """
    # Ordena tarefas de forma estável pelo PID apenas para exibição
    tasks = list(tasks)
    tasks.sort(key=lambda t: t.pid)

    # Horizonte de tempo
    max_t_tasks = _task_time_horizon(tasks)
    max_t_events = max([t for (t, _k, _p, _e) in events], default=0)
    max_t = max(max_t_tasks, max_t_events, horizon or 0)
    if max_t <= 0:
        max_t = 1

    # Layout básico
    margin_left = 40
    margin_right = 40
    margin_top = 80
    margin_bottom = 40

    row_height = 26
    row_gap = 6
    n_rows = max(1, len(tasks))
    plot_top = margin_top + 40   # deixa espaço para legenda/ícones
    plot_height = n_rows * (row_height + row_gap)

    width = margin_left + max_t * svg_scale + margin_right
    height = plot_top + plot_height + margin_bottom

    def x_of(tick: int) -> float:
        return margin_left + tick * svg_scale

    def y_row(idx: int) -> float:
        return plot_top + idx * (row_height + row_gap)

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')

    # Fundo
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{COLOR_BG}" '
        f'stroke="{COLOR_CANVAS_BORDER}" stroke-width="0.8"/>'
    )

    # Grade vertical
    grid_top = plot_top - 4
    grid_bot = plot_top + plot_height + 4
    for k in range(0, max_t + 1):
        x = x_of(k)
        parts.append(
            f'<line x1="{x:.2f}" y1="{grid_top:.2f}" x2="{x:.2f}" y2="{grid_bot:.2f}" '
            f'stroke="{COLOR_GRID_MINOR}" stroke-width="1"/>'
        )

    # Eixo do tempo
    axis_y = plot_top + plot_height + 5
    parts.append(
        f'<line x1="{x_of(0):.2f}" y1="{axis_y:.2f}" x2="{x_of(max_t):.2f}" y2="{axis_y:.2f}" '
        f'stroke="{COLOR_AXIS}" stroke-width="1.4"/>'
    )
    # Ticks e labels
    for k in range(0, max_t + 1):
        x = x_of(k)
        parts.append(
            f'<line x1="{x:.2f}" y1="{axis_y:.2f}" x2="{x:.2f}" y2="{axis_y+6:.2f}" '
            f'stroke="{COLOR_AXIS}" stroke-width="1"/>'
        )
        if k == 0 or k == max_t or k % 1 == 0:
            parts.append(
                f'<text x="{x:.2f}" y="{axis_y+18:.2f}" font-size="12" '
                f'text-anchor="middle" dominant-baseline="hanging">{k}</text>'
            )

    # Desenho das barras de execução
    for idx, t in enumerate(tasks):
        y = y_row(idx)
        # label do PID
        parts.append(
            f'<text x="{margin_left-6:.2f}" y="{y + row_height/2:.2f}" font-size="14" '
            f'text-anchor="end" dominant-baseline="middle">{t.pid}</text>'
        )
        # segmentos
        for (s, e) in t.segments:
            if e <= s:
                continue
            x0 = x_of(s)
            w = (e - s) * svg_scale
            parts.append(
                f'<rect x="{x0:.2f}" y="{y:.2f}" width="{w:.2f}" height="{row_height:.2f}" '
                f'rx="6" ry="6" fill="{t.color}" stroke="{COLOR_BAR_BORDER}" stroke-width="1.2" opacity="0.95"/>'
            )

    # Linha de tempo atual (modo live)
    if current_t is not None:
        x = x_of(current_t)
        parts.append(
            f'<line x1="{x:.2f}" y1="{plot_top-10:.2f}" x2="{x:.2f}" y2="{plot_top+plot_height+10:.2f}" '
            f'stroke="#ff0000" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.9"/>'
        )

    # Ícones de eventos no topo
    icon_y = margin_top + 10
    for (tick, kind, pid, extra) in events:
        x = x_of(tick)
        if kind == "ARRIVAL":
            # triângulo apontando para baixo
            parts.append(
                f'<polygon points="{x-6:.2f},{icon_y:.2f} {x+6:.2f},{icon_y:.2f} {x:.2f},{icon_y+10:.2f}" '
                f'fill="{COLOR_ARRIVAL}" opacity="0.95"/>'
            )
        elif kind == "PREEMPT":
            parts.append(
                f'<line x1="{x:.2f}" y1="{plot_top-4:.2f}" x2="{x:.2f}" y2="{plot_top+plot_height+4:.2f}" '
                f'stroke="{COLOR_PREEMPT}" stroke-width="1.6" opacity="0.85"/>'
            )
        elif kind == "FINISH":
            parts.append(
                f'<polygon points="{x:.2f},{icon_y-2:.2f} {x+6:.2f},{icon_y+4:.2f} '
                f'{x:.2f},{icon_y+10:.2f} {x-6:.2f},{icon_y+4:.2f}" '
                f'fill="{COLOR_FINISH}" opacity="0.95"/>'
            )
        elif kind == "IO_START":
            parts.append(
                f'<circle cx="{x:.2f}" cy="{icon_y+5:.2f}" r="4" fill="{COLOR_IO_START}" opacity="0.95"/>'
            )
        elif kind == "IO_END":
            parts.append(
                f'<circle cx="{x:.2f}" cy="{icon_y+5:.2f}" r="4" fill="{COLOR_IO_END}" opacity="0.95"/>'
            )
        elif kind == "MUTEX_LOCK":
            # pequeno quadrado
            parts.append(
                f'<rect x="{x-4:.2f}" y="{icon_y+1:.2f}" width="8" height="8" '
                f'fill="{COLOR_MUTEX_LOCK}" opacity="0.95"/>'
            )
        elif kind == "MUTEX_UNLOCK":
            parts.append(
                f'<rect x="{x-4:.2f}" y="{icon_y+1:.2f}" width="8" height="8" '
                f'fill="{COLOR_MUTEX_UNLOCK}" opacity="0.95" stroke="{COLOR_MUTEX_LOCK}" stroke-width="1"/>'
            )
        elif kind == "MUTEX_BLOCK":
            # X vermelho
            parts.append(
                f'<line x1="{x-5:.2f}" y1="{icon_y+1:.2f}" x2="{x+5:.2f}" y2="{icon_y+11:.2f}" '
                f'stroke="{COLOR_MUTEX_BLOCK}" stroke-width="1.5"/>'
            )
            parts.append(
                f'<line x1="{x+5:.2f}" y1="{icon_y+1:.2f}" x2="{x-5:.2f}" y2="{icon_y+11:.2f}" '
                f'stroke="{COLOR_MUTEX_BLOCK}" stroke-width="1.5"/>'
            )
        elif kind == "MUTEX_WAKE":
            # triângulo apontando para cima
            parts.append(
                f'<polygon points="{x:.2f},{icon_y+1:.2f} {x+6:.2f},{icon_y+11:.2f} {x-6:.2f},{icon_y+11:.2f}" '
                f'fill="{COLOR_MUTEX_WAKE}" opacity="0.95"/>'
            )

    # Legenda simples
    legend_w = 380
    legend_h = 70
    legend_x = (width - legend_w) / 2
    legend_y = margin_top - legend_h - 8
    if legend_y < 4:
        legend_y = 4

    parts.append(
        f'<g transform="translate({legend_x:.2f},{legend_y:.2f})">'
        f'<rect x="0" y="0" width="{legend_w:.2f}" height="{legend_h:.2f}" '
        f'fill="{LEGEND_BG_HEX}" stroke="{LEGEND_BORDER_HEX}" stroke-width="1.0" rx="10" ry="10"/>'
    )

    lx = 12.0
    ly = 16.0
    dy = 14.0

    # Chegada
    parts.append(
        f'<polygon points="{lx-6:.2f},{ly-5:.2f} {lx+6:.2f},{ly-5:.2f} {lx:.2f},{ly+5:.2f}" '
        f'fill="{COLOR_ARRIVAL}"/>'
    )
    parts.append(
        f'<text x="{lx+14:.2f}" y="{ly:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Chegada</text>'
    )

    # Preempção
    ly += dy
    parts.append(
        f'<line x1="{lx-6:.2f}" y1="{ly:.2f}" x2="{lx+6:.2f}" y2="{ly:.2f}" '
        f'stroke="{COLOR_PREEMPT}" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{lx+14:.2f}" y="{ly:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Preempção</text>'
    )

    # Término
    ly += dy
    parts.append(
        f'<polygon points="{lx:.2f},{ly-4:.2f} {lx+6:.2f},{ly:.2f} {lx:.2f},{ly+4:.2f} {lx-6:.2f},{ly:.2f}" '
        f'fill="{COLOR_FINISH}"/>'
    )
    parts.append(
        f'<text x="{lx+14:.2f}" y="{ly:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Término</text>'
    )

    # Segunda coluna: IO e Mutex
    lx2 = legend_w / 2 + 10.0
    ly2 = 16.0

    # IO_START / IO_END
    parts.append(
        f'<circle cx="{lx2:.2f}" cy="{ly2-2:.2f}" r="4" fill="{COLOR_IO_START}"/>'
    )
    parts.append(
        f'<circle cx="{lx2+14:.2f}" cy="{ly2-2:.2f}" r="4" fill="{COLOR_IO_END}"/>'
    )
    parts.append(
        f'<text x="{lx2+30:.2f}" y="{ly2:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Início/Fim E/S</text>'
    )

    # Mutex lock/unlock
    ly2 += dy
    parts.append(
        f'<rect x="{lx2-6:.2f}" y="{ly2-6:.2f}" width="8" height="8" fill="{COLOR_MUTEX_LOCK}"/>'
    )
    parts.append(
        f'<rect x="{lx2+6:.2f}" y="{ly2-6:.2f}" width="8" height="8" '
        f'fill="{COLOR_MUTEX_UNLOCK}" stroke="{COLOR_MUTEX_LOCK}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{lx2+24:.2f}" y="{ly2:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Lock/Unlock mutex</text>'
    )

    # Mutex block/wake
    ly2 += dy
    parts.append(
        f'<line x1="{lx2-6:.2f}" y1="{ly2-6:.2f}" x2="{lx2+6:.2f}" y2="{ly2+6:.2f}" '
        f'stroke="{COLOR_MUTEX_BLOCK}" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{lx2+6:.2f}" y1="{ly2-6:.2f}" x2="{lx2-6:.2f}" y2="{ly2+6:.2f}" '
        f'stroke="{COLOR_MUTEX_BLOCK}" stroke-width="1.5"/>'
    )
    parts.append(
        f'<polygon points="{lx2+18:.2f},{ly2-6:.2f} {lx2+24:.2f},{ly2+6:.2f} {lx2+12:.2f},{ly2+6:.2f}" '
        f'fill="{COLOR_MUTEX_WAKE}"/>'
    )
    parts.append(
        f'<text x="{lx2+34:.2f}" y="{ly2:.2f}" font-size="12" '
        f'text-anchor="start" dominant-baseline="middle">Block/Wake mutex</text>'
    )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)
