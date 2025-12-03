from typing import List, Tuple, Optional
from ..core import TCB

# ==== CONFIG VISUAL (fácil de ajustar) ====
COLOR_BG            = "#ffffff"
COLOR_CANVAS_BORDER = "#111111"
COLOR_GRID_MINOR    = "#e9e9e9"
COLOR_AXIS          = "#000000"
COLOR_BAR_BORDER    = "#333333"

COLOR_ARRIVAL       = "#1f78b4"   # triângulo (chegada)
COLOR_PREEMPT       = "#760eff"   # linha (preempção)
COLOR_FINISH        = "#000000"   # losango (término)

# Caixa da legenda (use hex + fill-opacity para compatibilidade SVG 1.1)
LEGEND_BG_HEX       = "#ffffff"
LEGEND_BG_OPACITY   = 0.88
LEGEND_BORDER       = "#444444"
LEGEND_W            = 260         # largura (ajusta tudo automaticamente)
LEGEND_H            = 32          # altura
LEGEND_MARGIN_TOP   = 6           # espaço entre topo e legenda
LEGEND_RADIUS       = 4           # cantos arredondados
LEGEND_FONT         = 12          # tamanho do texto
# ==========================================


def gantt_svg(
    tasks: List[TCB],
    events: List[Tuple[int, str, str, dict]] | None = None,
    svg_scale: int = 24,         # px por tick
    row_height: int = 24,        # altura por trilha
    margin: int = 40,            # margens
    show_minor_grid: bool = True, # grade secundária
    current_t: Optional[int] = None,   # STEP: tick correntemente exibido
    horizon: Optional[int] = None,     # STEP: mostrar escala total
    running: Optional[TCB] = None,     # STEP: desenhar bloco parcial do running
) -> str:
    """
    Gantt SVG com:
      - faixa superior para marcadores (chegada/preempção/término)
      - legenda em caixa acima, centralizada automaticamente (3 colunas)
      - grade, eixo do tempo e barras com cantos arredondados
    Args:
        tasks: List[TCB] - Tarefas a serem plotadas
        events: List[Tuple] - Eventos para marcação no gráfico
        svg_scale: int - Pixels por tick (default: 24)
        row_height: int - Altura de cada linha (default: 24)
        current_t: Optional[int] - Tick atual (para modo passo)
        horizon: Optional[int] - Horizonte total para escala
        running: Optional[TCB] - Tarefa em execução (para segmento parcial)
    """
    svg_scale  = max(6, int(svg_scale))
    row_height = max(18, int(row_height))
    margin     = max(24, int(margin))

    # 1) Dimensões
    max_t = 0
    for t in tasks:
        for a, b in t.segments:
            if b is not None:
                max_t = max(max_t, b)
    # considera também current_t e horizon para o limite do eixo
    if current_t is not None:
        max_t = max(max_t, current_t)
    if horizon is not None:
        max_t = max(max_t, horizon)

    n_rows      = len(tasks)
    marker_band = 24
    plot_top    = margin + marker_band
    plot_height = n_rows * row_height
    width       = margin + max_t * svg_scale + margin
    height      = plot_top + plot_height + margin

    # Helpers
    def x_of(tick: int) -> int:
        return margin + tick * svg_scale

    def y_row(idx: int) -> int:
        return plot_top + idx * row_height

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    # Canvas
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="{COLOR_BG}" stroke="{COLOR_CANVAS_BORDER}" stroke-width="0.8"/>'
    )

    # 2) Grade
    grid_top = plot_top - 4
    grid_bot = plot_top + plot_height + 4
    if show_minor_grid:
        for k in range(0, max_t + 1):
            x = x_of(k)
            parts.append(f'<line x1="{x}" y1="{grid_top}" x2="{x}" y2="{grid_bot}" stroke="{COLOR_GRID_MINOR}" stroke-width="1"/>')

    # Eixo do tempo (ticks "bonitos", ~10 rótulos)
    target_labels = 10
    step = max(1, (max_t // target_labels) or 1)
    def _nice(n: int) -> int:
        for s in (1, 2, 5):
            if n <= s: return s
        return 10
    if step > 5:
        pow10 = 1
        while step > 10:
            step //= 10
            pow10 *= 10
        step = _nice(step) * pow10

    axis_y = plot_top + plot_height + 8
    parts.append(f'<line x1="{margin}" y1="{axis_y}" x2="{x_of(max_t)}" y2="{axis_y}" stroke="{COLOR_AXIS}" stroke-width="1"/>')
    for k in range(0, max_t + 1, step):
        x = x_of(k)
        parts.append(f'<line x1="{x}" y1="{axis_y - 6}" x2="{x}" y2="{axis_y + 6}" stroke="{COLOR_AXIS}" stroke-width="1"/>')
        parts.append(f'<text x="{x}" y="{axis_y + 18}" font-family="monospace" font-size="11" text-anchor="middle">{k}</text>')

    # 3) Linhas (PIDs) e barras
    for idx, t in enumerate(sorted(tasks, key=lambda x: x.pid)):
        y = y_row(idx)
        parts.append(f'<text x="{margin - 8}" y="{y + row_height*0.65:.1f}" font-size="12" text-anchor="end">{t.pid}</text>')
        for a, b in t.segments:
            # Se current_t fornecido, desenhar apenas até current_t
            end = b
            if current_t is not None and b > current_t:
                end = current_t
            if a >= end:
                continue
            x = x_of(a)
            w = max(1, (end - a) * svg_scale)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{row_height - 6}" '
                f'rx="4" ry="4" fill="{t.color}" opacity="0.9" stroke="{COLOR_BAR_BORDER}" stroke-width="0.6"/>'
            )
        # bloco parcial do running (STEP): [last_started_at, current_t)
        if running is not None and t is running and current_t is not None:
            if getattr(t, "last_started_at", None) is not None and t.last_started_at < current_t:
                x = x_of(t.last_started_at)
                w = max(1, (current_t - t.last_started_at) * svg_scale)
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{row_height - 6}" '
                    f'rx="4" ry="4" fill="{t.color}" opacity="0.55" stroke="{COLOR_BAR_BORDER}" stroke-dasharray="2,2" stroke-width="0.6"/>'
                )
 
    # 4) Marcadores (faixa superior)
    if events:
        top_y = margin + 6
        for (tick, kind, pid, extra) in events:
            # Filtrar eventos que estão no futuro em relação ao current_t
            if current_t is not None and tick > current_t:
                continue
            x = x_of(tick)
            if kind == "ARRIVAL":
                parts.append(f'<polygon points="{x-6},{top_y} {x+6},{top_y} {x},{top_y+10}" fill="{COLOR_ARRIVAL}" opacity="0.95"/>')
            elif kind == "PREEMPT":
                parts.append(f'<line x1="{x}" y1="{plot_top - 4}" x2="{x}" y2="{plot_top + plot_height + 4}" stroke="{COLOR_PREEMPT}" stroke-width="1.6" opacity="0.85"/>')
            elif kind == "FINISH":
                parts.append(f'<polygon points="{x},{top_y-2} {x+6},{top_y+4} {x},{top_y+10} {x-6},{top_y+4}" fill="{COLOR_FINISH}" opacity="0.95"/>')

        # 5) Legenda — centralizada no SVG inteiro e com clamp às margens
        legend_y = max(6, margin - LEGEND_H - LEGEND_MARGIN_TOP)

        # Centro alvo: meio do SVG inteiro
        cx_svg = width / 2.0

        # Converte para coordenada do canto esquerdo da caixa
        x_left = cx_svg - LEGEND_W / 2.0

        # Clamp para não invadir as margens
        min_left = margin
        max_left = width - margin - LEGEND_W
        if x_left < min_left:
            x_left = min_left
        if x_left > max_left:
            x_left = max_left

        # Agrupamos a legenda e desenhamos tudo relativo ao centro da caixa
        cx = x_left + LEGEND_W / 2.0
        parts.append(f'<g transform="translate({cx:.2f},{legend_y:.2f})">')

        # Caixa da legenda
        parts.append(
            f'<rect x="{-LEGEND_W/2:.2f}" y="0" width="{LEGEND_W}" height="{LEGEND_H}" '
            f'fill="{LEGEND_BG_HEX}" fill-opacity="{LEGEND_BG_OPACITY}" '
            f'stroke="{LEGEND_BORDER}" stroke-width="0.8" '
            f'rx="{LEGEND_RADIUS}" ry="{LEGEND_RADIUS}"/>'
        )

        # Layout interno (3 colunas igualmente espaçadas)
        pad = 10
        inner_w = max(0, LEGEND_W - 2 * pad)
        centers = [
            -LEGEND_W/2 + pad + inner_w * (1/6),  # Chegada
            -LEGEND_W/2 + pad + inner_w * (3/6),  # Preempção
            -LEGEND_W/2 + pad + inner_w * (5/6),  # Término
        ]
        cy = LEGEND_H / 2.0  # centro vertical

        # Chegada (triângulo + texto)
        c0 = centers[0]
        parts.append(f'<polygon points="{c0-16:.2f},{cy-6:.2f} {c0-4:.2f},{cy-6:.2f} {c0-10:.2f},{cy+6:.2f}" fill="{COLOR_ARRIVAL}"/>')
        parts.append(f'<text x="{c0+2:.2f}" y="{cy:.2f}" font-size="{LEGEND_FONT}" text-anchor="start" dominant-baseline="middle">Chegada</text>')

        # Preempção (linha + texto)
        c1 = centers[1]
        parts.append(f'<line x1="{c1-16:.2f}" y1="{cy:.2f}" x2="{c1-2:.2f}" y2="{cy:.2f}" stroke="{COLOR_PREEMPT}" stroke-width="2"/>')
        parts.append(f'<text x="{c1+2:.2f}" y="{cy:.2f}" font-size="{LEGEND_FONT}" text-anchor="start" dominant-baseline="middle">Preempção</text>')

        # Término (losango + texto)
        c2 = centers[2]
        parts.append(f'<polygon points="{c2-12:.2f},{cy:.2f} {c2-6:.2f},{cy+6:.2f} {c2:.2f},{cy:.2f} {c2-6:.2f},{cy-6:.2f}" fill="{COLOR_FINISH}"/>')
        parts.append(f'<text x="{c2+2:.2f}" y="{cy:.2f}" font-size="{LEGEND_FONT}" text-anchor="start" dominant-baseline="middle">Término</text>')

        parts.append('</g>')
        
    parts.append("</svg>")
    return "\n".join(parts)
