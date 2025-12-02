import argparse, sys, pathlib, json, csv
from typing import List
from scheduler.core import TCB, SimulationEngine
from scheduler.algorithms.fifo import FIFO
from scheduler.algorithms.srtf import SRTF
from scheduler.algorithms.priop import PRIOP
from scheduler.io.config_parser import parse_config_text
from scheduler.viz.ascii import gantt_ascii
from scheduler.viz.svg import gantt_svg
import cairosvg
import multiprocessing as mp
import os

ALGOS = {
    "FIFO": FIFO,
    "SRTF": SRTF,
    "PRIOP": PRIOP,
}

# ------------------ HistoryManager para avançar/retroceder a simulação ------------------

class HistoryManager:
    """Gerencia histórico de snapshots para avançar/retroceder."""
    
    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        self.history: List[dict] = [engine.snapshot()]  # Estado inicial
        self.current_idx = 0
    
    def forward(self) -> bool:
        """Avança um passo, se possível."""
        # Verificar se já está no final do histórico
        if self.current_idx < len(self.history) - 1:
            # Já existe estado futuro: restaurar
            self.current_idx += 1
            self.engine.restore(self.history[self.current_idx])
            return True
        
        # Verificar se simulação terminou
        if (not self.engine.tasks_all and 
            not self.engine.ready and 
            self.engine.running is None):
            return False  # Não há para onde avançar
        
        # Avançar normalmente
        self.engine.step()
        
        # Salvar novo snapshot (descartando estados futuros se existirem)
        if self.current_idx < len(self.history) - 1:
            self.history = self.history[:self.current_idx + 1]
        
        self.history.append(self.engine.snapshot())
        self.current_idx = len(self.history) - 1
        return True
    
    def backward(self) -> bool:
        """Retrocede um passo, se possível."""
        if self.current_idx > 0:
            self.current_idx -= 1
            self.engine.restore(self.history[self.current_idx])
            return True
        return False

# ------------------ Viewer de PNG “live” em processo separado ------------------

def _viewer_main(png_path: str, title: str, refresh_ms: int = 120):
    """
    Processo filho: abre uma janela Tk e atualiza a imagem quando o arquivo PNG
    muda de mtime. Mantém referência da imagem para evitar GC do Tkinter.
    """
    import tkinter as _tk
    from PIL import Image as _Image, ImageTk as _ImageTk

    root = _tk.Tk()
    root.title(title)
    try:
        root.attributes("-type", "splash")  # pode não ser suportado em todos os WMs
    except Exception:
        pass

    label = _tk.Label(root, bd=0, highlightthickness=0)
    label.pack()

    state = {"photo": None, "mt": None, "w": 800, "h": 500}

    def _try_load():
        try:
            mt = os.path.getmtime(png_path)
        except OSError:
            root.after(refresh_ms, _try_load)
            return

        if state["mt"] != mt:
            try:
                im = _Image.open(png_path)
                im.load()  # garante leitura completa
                photo = _ImageTk.PhotoImage(im)
                label.configure(image=photo)
                state["photo"] = photo
                state["mt"] = mt

                w, h = im.width, im.height
                if (w, h) != (state["w"], state["h"]):
                    state["w"], state["h"] = w, h
                    # não use geometry: deixa o Tk ajustar client area (evita corte no topo)
                    root.update_idletasks()
                    root.minsize(w, h)
            except Exception:
                pass

        root.after(refresh_ms, _try_load)

    root.after(0, _try_load)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


def spawn_viewer(png_path: str, title: str = "Gráfico Gantt - Live", refresh_ms: int = 120) -> mp.Process:
    """Sobe o viewer em outro processo (daemon)."""
    proc = mp.Process(target=_viewer_main, args=(png_path, title, refresh_ms), daemon=True)
    proc.start()
    return proc


def stop_viewer(proc: mp.Process | None) -> None:
    """Encerra o viewer com segurança (se ainda estiver vivo)."""
    if proc is not None and proc.is_alive():
        proc.terminate()
        try:
            proc.join(timeout=1.5)
        except Exception:
            pass


# ------------------ utilitários do simulador ------------------

def load_config(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    return parse_config_text(text)

def build_tcbs(cfg) -> List[TCB]:
    return [TCB(pid=t.pid, color=t.color, arrival=t.arrival, duration=t.duration, priority=t.priority, events=t.events) for t in cfg.tasks]

def write_summary(outdir: pathlib.Path, summary: dict):
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    rows = [{"pid": pid, **vals} for pid, vals in summary.items()]
    if rows:
        with (outdir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)

def write_results_tex(project_root: pathlib.Path, runs_meta: list):
    docs = project_root / "docs" / "latex" / "secoes"
    docs.mkdir(parents=True, exist_ok=True)
    lines = [r"%% AUTO-GERADO -- NÃO EDITAR MANUALMENTE", r"\\chapter{Resultados}"]
    for meta in runs_meta:
        algo = meta["algo"]
        summary_csv = meta["summary_csv"]
        lines.append(rf"\\section{{Resumo: {algo}}}")
        import csv as _csv
        rows = []
        with open(summary_csv, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            headers = reader.fieldnames or []
            for row in reader:
                rows.append(row)
        if not rows:
            lines.append("Sem dados.")
            continue
        cols = "|".join(["l"] * (len(headers)))
        lines.append(r"\\begin{table}[h]")
        lines.append(r"\\centering")
        lines.append(r"\\begin{tabular}{" + cols + "}")
        lines.append(r"\\hline")
        lines.append(" & ".join(headers) + r" \\\\ \\hline")
        for r in rows:
            lines.append(" & ".join(str(r[h]) for h in headers) + r" \\\\")
        lines.append(r"\\hline")
        lines.append(r"\\end{tabular}")
        lines.append(rf"\\caption{{Métricas por processo para {algo}.}}")
        lines.append(r"\\end{table}")
    (docs / "07-resultados.tex").write_text("\\n".join(lines), encoding="utf-8")

def prepare_scheduler(name: str, aging_step: int, tiebreaker: list[str]):
    if name == "PRIOP":
        sched = PRIOP(aging_step=aging_step)
    else:
        sched = ALGOS[name]()
    if hasattr(sched, "set_tiebreaker"):
        sched.set_tiebreaker(tiebreaker)
    return sched

def run_single(cfg_path: pathlib.Path, outdir: pathlib.Path, algo_name: str, tiebreaker: list[str], aging_step: int):
    cfg = load_config(cfg_path)
    scheduler = prepare_scheduler(algo_name, aging_step, tiebreaker)
    engine = SimulationEngine(build_tcbs(cfg), scheduler=scheduler, quantum=cfg.quantum, tiebreaker=tiebreaker)
    engine.run_full()
    outdir.mkdir(parents=True, exist_ok=True)
    svg = gantt_svg(engine.finished, events=engine.events, svg_scale=20)
    # Exibe o gráfico gerado após a simulação
    final_svg = outdir / "gantt.svg"
    if final_svg.exists():
        final_png = outdir / "gantt_final.png"
        cairosvg.svg2png(
            url=str(final_svg),
            write_to=str(final_png),
            output_width=1600,
            output_height=800,
        )
        _ = spawn_viewer(str(final_png), title="Gráfico Gantt - Resultado Final")
    (outdir / "gantt.svg").write_text(svg, encoding="utf-8")
    summary = engine.summary()
    write_summary(outdir, summary)
    import csv as _csv
    with (outdir / "events.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["t", "kind", "pid", "extra"])
        for (t, kind, pid, extra) in engine.events:
            w.writerow([t, kind, pid, extra])
    return {"algo": algo_name, "summary_csv": str(outdir / "summary.csv")}


# ------------------ CLI ------------------

def main(argv=None):
    # Evita herdar descritores/estado quando abrimos a janela (mais estável que 'fork')
    try:
        if mp.get_start_method(allow_none=True) != "spawn":
            mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    p = argparse.ArgumentParser(prog="scheduler-sim")
    sub = p.add_subparsers(dest="cmd")

    runp = sub.add_parser("run", help="Run a single simulation (default if no subcommand).")
    runp.add_argument("--config", required=True)
    runp.add_argument(
        "--algo",
        choices=["FIFO","SRTF","PRIOP"],
        help="Sobrescreve o algoritmo definido no arquivo (FIFO, SRTF, PRIOP)."
    )
    runp.add_argument("--mode", choices=["step","full"], default="full")
    runp.add_argument("--outdir", default=".")
    runp.add_argument("--tiebreaker", default="arrival,pid")
    runp.add_argument("--aging-step", type=int, default=0, help="Aging step (ticks por incremento de prioridade, PRIOP).")
    runp.add_argument("--report-latex", action="store_true", help="Atualiza docs/latex/secoes/07-resultados.tex desta execução.")

    cmpp = sub.add_parser("compare", help="Executa múltiplos algoritmos e gera LaTeX de resultados.")
    cmpp.add_argument("--config", required=True)
    cmpp.add_argument("--algos", default="FIFO,SRTF,PRIOP")
    cmpp.add_argument("--outdir", default="out_compare")
    cmpp.add_argument("--tiebreaker", default="arrival,pid")
    cmpp.add_argument("--aging-step", type=int, default=0)

    args = p.parse_args(argv)
    if args.cmd is None:
        args.cmd = "run"

    tiebreaker = [x.strip() for x in getattr(args, "tiebreaker", "arrival,pid").split(",") if x.strip()]
    cfg_path = pathlib.Path(getattr(args, "config", ""))
    base_out = pathlib.Path(getattr(args, "outdir", "out"))

    if args.cmd == "run":
        if args.mode == "step":
            cfg = load_config(cfg_path)
            algo_name = (args.algo or cfg.algorithm).upper()
            sched = prepare_scheduler(algo_name, getattr(args, "aging_step", 0), tiebreaker)
            tcbs = build_tcbs(cfg)
            engine = SimulationEngine(tcbs, scheduler=sched, quantum=cfg.quantum, tiebreaker=tiebreaker)

            # horizonte total para o eixo ASCII (máximo arrival+duration)
            horizon = max((t.arrival + t.duration) for t in tcbs) if tcbs else 0

            base_out.mkdir(parents=True, exist_ok=True)
            svg_step_dir = base_out / "out_step_svg"
            svg_step_dir.mkdir(parents=True, exist_ok=True)

            # arquivo PNG “ao vivo” que o viewer lerá e atualizará
            live_png = svg_step_dir / "live.png"
            viewer_proc = None

            history_mgr = HistoryManager(engine)
            print("== STEP MODE COM HISTÓRICO ==")
            print("Comandos disponíveis:")
            print("  [n]ext (ou Enter): Avança um passo")
            print("  [p]rev: Retrocede um passo")
            print("  [g]oto <n>: Vai para o passo específico")
            print("  [l]ist: Mostra resumo do histórico")
            print("  [s]tatus: Mostra status atual")
            print("  [q]uit: Sai da simulação")
            print("=" * 50)

            while True:
                # 1) Exibir estado atual
                info = history_mgr.get_current_info()
                print(f"\n=== Passo {info['current_step']}/{info['total_steps']} @ t={info['clock']} ===")
                
                state = {
                    "running": (engine.running.pid if engine.running else None),
                    "ready": [t.pid for t in sorted(engine.ready, key=lambda x: (x.arrival, x.pid))],
                    "finished": [t.pid for t in sorted(engine.finished, key=lambda x: x.pid)],
                }
                print(f"Estado: {state}")

                # 2) Exibir Gantt ASCII
                snapshot_tasks = engine.finished + engine.ready + ([engine.running] if engine.running else [])
                print(gantt_ascii(snapshot_tasks, current_t=engine.clock, horizon=horizon, running=engine.running))

                # 3) Gerar SVG e PNG "live"
                svg = gantt_svg(
                    snapshot_tasks,
                    events=engine.events,
                    svg_scale=24,
                    current_t=engine.clock,
                    horizon=horizon,
                    running=engine.running,
                )
                svg_path = svg_step_dir / f"gantt_t{engine.clock:04d}.svg"
                svg_path.write_text(svg, encoding="utf-8")

                cairosvg.svg2png(
                    url=str(svg_path),
                    write_to=str(live_png),
                    output_width=1400,
                    output_height=650,
                )

                # 4) Iniciar viewer no primeiro passo
                if viewer_proc is None:
                    viewer_proc = spawn_viewer(str(live_png), title="Gráfico Gantt - Live")
                    print("[info] Viewer iniciado. Atualizando gráfico...")

                # 5) Aguardar comando do usuário
                try:
                    cmd = input(f"\nPasso {history_mgr.current_idx}/{len(history_mgr.history)-1} @ t={engine.clock} (n/p/q): ").strip().lower()
                except KeyboardInterrupt:
                    print("\nInterrompido pelo usuário.")
                    break
                
                if cmd == '' or cmd == 'n':
                    # Avançar
                    if not history_mgr.forward():
                        print("Simulação finalizada. Não há mais passos para avançar.")
                elif cmd == 'p':
                    # Retroceder
                    if not history_mgr.backward():
                        print("Já no início do histórico.")
                elif cmd == 'q':
                    # Sair
                    print("Saindo do modo passo a passo...")
                    break
                else:
                    print("Comando inválido. Use: n (next), p (prev), q (quit)")

                print("\n== Simulação finalizada ==", flush=True)

            # Salvar informações em JSON
            trace_summary = []
            for idx, snapshot in enumerate(history_mgr.history):
                trace_summary.append({
                    "step": idx,
                    "clock": snapshot.get('clock', 0),
                    "running_pid": snapshot.get('running_pid'),
                    "ready_pids": snapshot.get('ready_pids', []),
                    "finished_pids": snapshot.get('finished_pids', [])
                })

            (base_out / "trace_summary.json").write_text(json.dumps(trace_summary, indent=2), encoding="utf-8")
            
            # Gerar SVG final
            svg = gantt_svg(engine.finished, events=engine.events, svg_scale=20)
            (base_out / "gantt.svg").write_text(svg, encoding="utf-8")
            
            # Salvar resumo
            summary = engine.summary()
            write_summary(base_out, summary)
            
            # Salvar eventos
            import csv as _csv
            with (base_out / "events.csv").open("w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f)
                w.writerow(["t", "kind", "pid", "extra"])
                for (t, kind, pid, extra) in engine.events:
                    w.writerow([t, kind, pid, extra])

            # Fechar viewer
            if viewer_proc is not None:
                stop_viewer(viewer_proc)

            return 0

        else:
            cfg_tmp = load_config(cfg_path)
            algo_name = (args.algo or cfg_tmp.algorithm).upper()
            meta = run_single(cfg_path, base_out, algo_name, tiebreaker, getattr(args, "aging_step", 0))

            cfg = load_config(cfg_path)
            cfg_algo = cfg.algorithm.upper()
            chosen_algo = args.algo.upper() if getattr(args, "algo", None) else cfg_algo
            if getattr(args, "algo", None) and chosen_algo != cfg_algo:
                print(f"[info] --algo={chosen_algo} sobrescreve o algoritmo do arquivo ({cfg_algo}).")

            meta = run_single(cfg_path, base_out, chosen_algo, tiebreaker, getattr(args, "aging_step", 0))

            if getattr(args, "report-latex", False):
                project_root = pathlib.Path(__file__).resolve().parents[1]
                write_results_tex(project_root, [meta])

            summary = json.loads((base_out / "summary.json").read_text(encoding="utf-8"))
            from pprint import pprint; pprint(summary)

            # Mostrar Gantt final (opcional)
            final_svg = base_out / "gantt.svg"
            if final_svg.exists():
                final_png = base_out / "gantt_final.png"
                cairosvg.svg2png(
                    url=str(final_svg),
                    write_to=str(final_png),
                    output_width=1600,
                    output_height=800,
                )
                _ = spawn_viewer(str(final_png), title="Gráfico Gantt - Resultado Final")

            return 0

    if args.cmd == "compare":
        algos = [a.strip().upper() for a in args.algos.split(",") if a.strip()]
        metas = []
        for algo in algos:
            out_algo = base_out / algo
            metas.append(run_single(cfg_path, out_algo, algo, tiebreaker, getattr(args, "aging_step", 0)))
        project_root = pathlib.Path(__file__).resolve().parents[1]
        write_results_tex(project_root, metas)
        print(f"LaTeX atualizado em: {project_root / 'docs' / 'latex' / 'secoes' / '07-resultados.tex'}")
        return 0

    print("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
