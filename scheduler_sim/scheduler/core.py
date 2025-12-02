from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Protocol
import copy

@dataclass
class TCB:
    pid: str
    color: str
    arrival: int
    duration: int
    priority: int = 1
    events: str = ""
    # runtime
    remaining: int = field(init=False)
    start_time: Optional[int] = None
    finish_time: Optional[int] = None
    response_time: Optional[int] = None
    waiting_accum: int = 0
    aging_wait: int = 0               # espera desde o último enfileiramento
    last_started_at: Optional[int] = None
    preemptions: int = 0
    segments: List[Tuple[int, int]] = field(default_factory=list)

    def __post_init__(self):
        self.remaining = self.duration
        # NOVO: FCFS estável — guarda o arrival original e a sequência de enfileiramento
        self.arrival_original: int = self.arrival
        self.enqueue_seq: int = -1

class Scheduler(Protocol):
    def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
        ...

def _tie_key(t: "TCB", order: list[str]):
    key = []
    for f in order:
        if f == "arrival":
            key.append(t.arrival)
        elif f == "pid":
            key.append(t.pid)
        elif f == "priority":
            key.append(t.priority)
        else:
            key.append(None)
    return tuple(key)

class SimulationEngine:
    """
    Single CPU, tick-based preemptive simulator.
    Deterministic tiebreakers used inside algorithms (default arrival,pid).
    The engine stores 'tiebreaker' for future use and reporting.
    """
    def __init__(self, tasks: List[TCB], scheduler: Scheduler, quantum: int = 2, tiebreaker: list[str] | None = None):
        self.clock = 0
        self.tasks_all: List[TCB] = sorted(tasks, key=lambda t: (t.arrival, t.pid))
        self.ready: List[TCB] = []
        self.running: Optional[TCB] = None
        self.finished: List[TCB] = []
        self.scheduler = scheduler
        self.quantum = quantum
        self.time_in_quantum = 0
        self.tiebreaker = tiebreaker or ['arrival','pid']
        # --- NEW: event log [(t, kind, pid, extra_dict)]
        self.events: List[Tuple[int, str, str, Dict]] = []
        # NOVO: contador global de enfileiramento para FCFS estável
        self._fifo_seq: int = 0

    # --- NEW: helper to append an event at current clock
    def _emit(self, kind: str, pid: Optional[str], **extra):
        self.events.append((self.clock, kind, pid or "", extra))

    def _admit_new_arrivals(self):
        for t in list(self.tasks_all):
            if t.arrival == self.clock:
                #t.aging_wait = 0 
                #self.ready.append(t)
                t.aging_wait = 0
                # FCFS estável: atribui sequência ao entrar na ready
                t.enqueue_seq = self._fifo_seq
                self._fifo_seq += 1
                self.ready.append(t)
                self.tasks_all.remove(t)
                # NEW
                self._emit("ARRIVAL", t.pid)

    def _dispatch(self, task: TCB):
        if task in self.ready:
            self.ready.remove(task)
        self.running = task
        if self.running.start_time is None:
            self.running.start_time = self.clock
        if self.running.response_time is None:
            self.running.response_time = self.clock - self.running.arrival
        self.running.last_started_at = self.clock
        self.running.aging_wait = 0              #começa a rodar, parou de “envelhecer”
        self.time_in_quantum = 0

    def _preempt_if_needed(self):
        chosen = self.scheduler.choose(self.ready, self.running, self.clock)
        if chosen is None and self.running is None:
            return
        if chosen is self.running:
            return
        if chosen is None and self.running is not None:
            return
        if chosen is not None:
            if self.running is not None and self.running.last_started_at is not None and self.running.last_started_at < self.clock:
                self.running.segments.append((self.running.last_started_at, self.clock))
                self.running.preemptions += 1
                #self.running.aging_wait = 0      #recomeça a contar aging na ready
                #self.ready.append(self.running)
                self.running.aging_wait = 0      # recomeça a contar aging na ready
                # FCFS estável: nova sequência ao voltar para a ready
                self.running.enqueue_seq = self._fifo_seq
                self._fifo_seq += 1
                self.ready.append(self.running)
            self._dispatch(chosen)
        if self.running is not None and chosen is not self.running:
            self._emit("PREEMPT", self.running.pid)

    def _tick_running(self):
        if self.running is None:
            return
        self.running.remaining -= 1
        self.time_in_quantum += 1
        if self.running.remaining == 0:
            if self.running.last_started_at is not None:
                self.running.segments.append((self.running.last_started_at, self.clock + 1))
            self.running.finish_time = self.clock + 1
            self.finished.append(self.running)
            # NEW
            #self._emit("FINISH", self.running.pid)
            # Corrige FINISH para sair no instante de fim exclusivo (clock+1)
            self.events.append((self.clock + 1, "FINISH", self.running.pid, {}))
            self.running = None
            self.time_in_quantum = 0

    def _update_waiting(self):
        for t in self.ready:
            if t.arrival <= self.clock:
                t.waiting_accum += 1
                if hasattr(t, "aging_wait"):
                    t.aging_wait += 1    # para aging efetivo

    def step(self) -> None:
        if not self.tasks_all and not self.ready and self.running is None:
            return  # Simulação terminou, não faz nada
        self._admit_new_arrivals()
        self._preempt_if_needed()
        self._tick_running()
        self._update_waiting()
        self.clock += 1
        if self.running is None and (self.ready or self.tasks_all):
            self._admit_new_arrivals()
            self._preempt_if_needed()

    def run_full(self):
        while self.tasks_all or self.ready or self.running is not None:
            self.step()

    def summary(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for t in sorted(self.finished, key=lambda x: x.pid):
            turnaround = (t.finish_time - t.arrival) if t.finish_time is not None else None
            out[t.pid] = {
                "arrival": t.arrival,
                "duration": t.duration,
                "start": (-1 if t.start_time is None else t.start_time),
                "finish": (-1 if t.finish_time is None else t.finish_time),
                "waiting": t.waiting_accum,
                "turnaround": (-1 if turnaround is None else turnaround),
                "response": (-1 if t.response_time is None else t.response_time),
                "preemptions": t.preemptions,
            }
        return out
    
    def snapshot(self) -> dict:
        """
        Retorna uma cópia do estado atual do engine.
        """
        # Coletar todos os TCBs únicos do sistema
        tcb_dict = {}

        # Coletar todos os TCBs únicos usando PID como chave
        for t in self.tasks_all:
            tcb_dict[t.pid] = t
        for t in self.ready:
            tcb_dict[t.pid] = t
        for t in self.finished:
            tcb_dict[t.pid] = t
        if self.running is not None:
            tcb_dict[self.running.pid] = self.running
        
        # Criar cópias de cada TCB
        tcb_copies = {}
        for pid, tcb in tcb_dict.items():
            tcb_copies[pid] = copy.deepcopy(tcb)
        
        # Mapear listas para PIDs
        return {
            'clock': self.clock,
            'tasks_all_pids': [t.pid for t in self.tasks_all],
            'ready_pids': [t.pid for t in self.ready],
            'finished_pids': [t.pid for t in self.finished],
            'running_pid': self.running.pid if self.running else None,
            'time_in_quantum': self.time_in_quantum,
            'events': copy.deepcopy(self.events),
            '_fifo_seq': self._fifo_seq,
            'tcb_copies': tcb_copies,
        }
    
    def restore(self, snapshot: dict) -> None:
        """
        Restaura o estado do engine a partir de um snapshot.
        """
        tcb_copies = snapshot['tcb_copies']
        
        # Reconstruir listas a partir dos PIDs
        self.tasks_all = [tcb_copies[pid] for pid in snapshot['tasks_all_pids']]
        self.ready = [tcb_copies[pid] for pid in snapshot['ready_pids']]
        self.finished = [tcb_copies[pid] for pid in snapshot['finished_pids']]
        self.running = tcb_copies.get(snapshot['running_pid']) if snapshot['running_pid'] else None
        
        # Restaurar atributos simples
        self.clock = snapshot['clock']
        self.time_in_quantum = snapshot['time_in_quantum']
        self.events = snapshot['events']
        self._fifo_seq = snapshot['_fifo_seq']
