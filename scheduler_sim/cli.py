import argparse, sys, pathlib, json, csv
from typing import List
from .scheduler.core import TCB, SimulationEngine
from .scheduler.algorithms.fifo import FIFO
from .scheduler.algorithms.srtf import SRTF
from .scheduler.algorithms.priop import PRIOP
from .scheduler.io.config_parser import parse_config_text
from .scheduler.viz.ascii import gantt_ascii
from .scheduler.viz.svg import gantt_svg

ALGOS = {
    "FIFO": FIFO,
    "SRTF": SRTF,
    "PRIOP": PRIOP,
}

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
    # NEW: pass events, optional svg_scale default=20
    svg = gantt_svg(engine.finished, events=engine.events, svg_scale=20)
    (outdir / "gantt.svg").write_text(svg, encoding="utf-8")
    summary = engine.summary()
    write_summary(outdir, summary)
    # NEW: write events.csv
    import csv as _csv
    with (outdir / "events.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["t", "kind", "pid", "extra"])
        for (t, kind, pid, extra) in engine.events:
            w.writerow([t, kind, pid, extra])
    return {"algo": algo_name, "summary_csv": str(outdir / "summary.csv")}

def main(argv=None):
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
    # permite escolher o algoritmo diretamente no run
    # runp.add_argument("--algo", choices=["FIFO","SRTF","PRIOP"], help="Override do algoritmo do arquivo de configuração.")
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
            #engine = SimulationEngine(build_tcbs(cfg), scheduler=sched, quantum=cfg.quantum, tiebreaker=tiebreaker)
            # tcbs = build_tcbs(cfg)
            # engine = SimulationEngine(tcbs, scheduler=sched, quantum=cfg.quantum, tiebreaker=tiebreaker)
            tcbs = build_tcbs(cfg)
            engine = SimulationEngine(tcbs, scheduler=sched, quantum=cfg.quantum, tiebreaker=tiebreaker)
            # horizonte total para o eixo ASCII (máximo arrival+duration)
            horizon = max((t.arrival + t.duration) for t in tcbs) if tcbs else 0
            base_out.mkdir(parents=True, exist_ok=True)
            svg_step_dir = base_out / "out_step_svg"
            svg_step_dir.mkdir(parents=True, exist_ok=True)
            print("== STEP MODE: Enter para avançar 1 tick; Ctrl+C para sair ==")
            trace = []
            while engine.tasks_all or engine.ready or engine.running is not None:
                try:
                    input(f"[t={engine.clock}] Continue? ")
                except KeyboardInterrupt:
                    break
                # state = {
                #     "t": engine.clock,
                #     "running": (engine.running.pid if engine.running else None),
                #     "ready": [t.pid for t in sorted(engine.ready, key=lambda x: (x.arrival, x.pid))],
                #     "finished": [t.pid for t in sorted(engine.finished, key=lambda x: x.pid)],
                # }
                # trace.append(state)
                # engine.step()
                # print("STATE:", state)
                # print(gantt_ascii(engine.finished + engine.ready + ([engine.running] if engine.running else [])))
                # Avança a simulação ANTES de capturar/imprimir o estado,
                # assim 't' refletirá o tick já executado (alinhado ao Gantt).
                engine.step()
                state = {
                    "t": engine.clock,
                    "running": (engine.running.pid if engine.running else None),
                    "ready": [t.pid for t in sorted(engine.ready, key=lambda x: (x.arrival, x.pid))],
                    "finished": [t.pid for t in sorted(engine.finished, key=lambda x: x.pid)],
                }
                trace.append(state)
                # print(f"STATE@t={engine.clock}:", state)
                # print(gantt_ascii(engine.finished + engine.ready + ([engine.running] if engine.running else []), current_t=engine.clock))
                print(f"STATE@t={engine.clock}:", state)
                # snapshot visual: finished + ready + (running se houver),
                # com eixo até 'horizon' e bloco parcial do running
                snapshot_tasks = engine.finished + engine.ready + ([engine.running] if engine.running else [])
                print(gantt_ascii(snapshot_tasks, current_t=engine.clock, horizon=horizon, running=engine.running))
                # snapshot SVG por tick (vivo): inclui bloco parcial do running e horizonte total
                svg = gantt_svg(
                    snapshot_tasks,
                    events=engine.events,
                    svg_scale=24,
                    current_t=engine.clock,
                    horizon=horizon,
                    running=engine.running,
                )
                #(base_out / "gantt_step.svg")
                (svg_step_dir / f"gantt_t{engine.clock:04d}.svg").write_text(svg, encoding="utf-8")
            (base_out / "trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
            # gerar artefatos finais também no STEP
            svg = gantt_svg(engine.finished, events=engine.events, svg_scale=20)
            (base_out / "gantt.svg").write_text(svg, encoding="utf-8")
            summary = engine.summary()
            write_summary(base_out, summary)
            import csv as _csv
            with (base_out / "events.csv").open("w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f)
                w.writerow(["t", "kind", "pid", "extra"])
                for (t, kind, pid, extra) in engine.events:
                    w.writerow([t, kind, pid, extra])

            return 0
        else:
            #meta = run_single(cfg_path, base_out, load_config(cfg_path).algorithm.upper(), tiebreaker, getattr(args, "aging_step", 0))
            # FULL: honra --algo quando presente; caso contrário, usa o cabeçalho do arquivo
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
