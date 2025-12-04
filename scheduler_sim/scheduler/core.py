
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Protocol


@dataclass
class TaskEvent:
    """Represents a single per-task event (I/O or mutex).

    All times are relative to the start of the task's execution, as specified
    in the configuration file.
    """
    kind: str          # "IO", "ML" (mutex lock) or "MU" (mutex unlock)
    at: int            # time offset relative to task start
    duration: Optional[int] = None
    resource_id: Optional[int] = None


@dataclass
class TCB:
    pid: str
    color: str
    arrival: int
    duration: int
    priority: int = 1
    events: List[TaskEvent] = field(default_factory=list)
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
    # total CPU time consumed so far (for relative event timings)
    cpu_time: int = 0
    # remaining time in an ongoing I/O operation (0 when not in I/O)
    io_remaining: int = 0
    # reason for being blocked (e.g. "IO", "MUTEX"), or None when ready/running
    blocked_reason: Optional[str] = None

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
        # tasks currently blocked (e.g., performing I/O or waiting on mutex)
        self.blocked: List[TCB] = []
        # mutex id -> owner TCB (or None if unlocked)
        self.mutex_owner: Dict[int, Optional[TCB]] = {}
        # mutex id -> FIFO wait queue of TCBs
        self.mutex_wait_queues: Dict[int, List[TCB]] = {}
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


    def _update_blocked_io(self) -> None:
        """
        Advance I/O for all tasks blocked on I/O. When an I/O finishes, the task
        is moved back to the ready queue and can be chosen again by the scheduler.
        """
        new_ready: List[TCB] = []
        still_blocked: List[TCB] = []
        for t in self.blocked:
            if t.blocked_reason == "IO" and t.io_remaining > 0:
                t.io_remaining -= 1
                if t.io_remaining == 0:
                    # I/O finished exactly at the end of this tick (exclusive time self.clock+1)
                    t.blocked_reason = None
                    # reset aging counters when it re-enters ready
                    t.aging_wait = 0
                    t.enqueue_seq = self._fifo_seq
                    self._fifo_seq += 1
                    new_ready.append(t)
                    # log I/O end at (clock+1), symmetrically with FINISH
                    self.events.append((self.clock + 1, "IO_END", t.pid, {}))
                else:
                    still_blocked.append(t)
            else:
                # Other kinds of blocked (e.g., mutex) will be handled in future extensions.
                still_blocked.append(t)
        if new_ready:
            self.ready.extend(new_ready)
        self.blocked = still_blocked

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

    def _tick_running(self):
        if self.running is None:
            return
        # 1) Avança o consumo de CPU desta tarefa (tempo relativo e restante)
        self.running.cpu_time += 1
        self.running.remaining -= 1
        self.time_in_quantum += 1

        # 2) Eventos de mutex (lock/unlock) que ocorrem exatamente após este tick
        for ev in self.running.events:
            if ev.at != self.running.cpu_time:
                continue
            # Solicitação de mutex (lock)
            if ev.kind == "ML" and ev.resource_id is not None:
                mid = ev.resource_id
                owner = self.mutex_owner.get(mid)
                if owner is None or owner is self.running:
                    # Mutex livre (ou já com o próprio dono) -> adquire/continua
                    self.mutex_owner[mid] = self.running
                    self.events.append((self.clock + 1, "MUTEX_LOCK", self.running.pid, {"mid": mid}))
                else:
                    # Mutex ocupado -> bloqueia tarefa na fila do mutex
                    if self.running.last_started_at is not None:
                        self.running.segments.append((self.running.last_started_at, self.clock + 1))
                    self.running.blocked_reason = "MUTEX"
                    q = self.mutex_wait_queues.setdefault(mid, [])
                    q.append(self.running)
                    self.events.append((self.clock + 1, "MUTEX_BLOCK", self.running.pid, {"mid": mid}))
                    self.blocked.append(self.running)
                    self.running = None
                    self.time_in_quantum = 0
                    return
            # Liberação de mutex (unlock)
            elif ev.kind == "MU" and ev.resource_id is not None:
                mid = ev.resource_id
                owner = self.mutex_owner.get(mid)
                if owner is self.running:
                    # Libera mutex
                    self.events.append((self.clock + 1, "MUTEX_UNLOCK", self.running.pid, {"mid": mid}))
                    q = self.mutex_wait_queues.get(mid) or []
                    if q:
                        # Acorda próxima tarefa na fila
                        next_t = q.pop(0)
                        self.mutex_wait_queues[mid] = q
                        self.mutex_owner[mid] = next_t
                        # Remove da lista de bloqueados e reinicializa estado de pronto
                        if next_t in self.blocked:
                            self.blocked.remove(next_t)
                        next_t.blocked_reason = None
                        next_t.aging_wait = 0
                        next_t.enqueue_seq = self._fifo_seq
                        self._fifo_seq += 1
                        self.ready.append(next_t)
                        self.events.append((self.clock + 1, "MUTEX_WAKE", next_t.pid, {"mid": mid}))
                    else:
                        # Ninguém esperando -> mutex fica livre
                        self.mutex_owner[mid] = None
                else:
                    # Evento MU para tarefa que não é dona do mutex: ignora silenciosamente
                    pass

        # 3) Verifica término da tarefa
        if self.running.remaining == 0:
            if self.running.last_started_at is not None:
                self.running.segments.append((self.running.last_started_at, self.clock + 1))
            self.running.finish_time = self.clock + 1
            self.finished.append(self.running)
            # Corrige FINISH para sair no instante de fim exclusivo (clock+1)
            self.events.append((self.clock + 1, "FINISH", self.running.pid, {}))
            self.running = None
            self.time_in_quantum = 0
            return

        # 4) Verifica se algum evento de I/O deve disparar exatamente após este tick
        for ev in self.running.events:
            if ev.kind == "IO" and ev.at == self.running.cpu_time:
                # Fecha o segmento de CPU até o fim deste tick
                if self.running.last_started_at is not None:
                    self.running.segments.append((self.running.last_started_at, self.clock + 1))
                # Coloca tarefa em I/O
                self.running.blocked_reason = "IO"
                self.running.io_remaining = ev.duration or 0
                # Registra início de I/O no instante exclusivo (clock+1)
                self.events.append((self.clock + 1, "IO_START", self.running.pid, {"duration": self.running.io_remaining}))
                # Move para fila de bloqueadas e libera a CPU
                self.blocked.append(self.running)
                self.running = None
                self.time_in_quantum = 0
                return

    def _update_waiting(self):
        for t in self.ready:
            if t.arrival <= self.clock:
                t.waiting_accum += 1
                if hasattr(t, "aging_wait"):
                    t.aging_wait += 1    # para aging efetivo

    def step(self) -> None:
        # 1) Admit new arrivals at the current clock
        self._admit_new_arrivals()
        # 2) Advance I/O of blocked tasks (if any)
        self._update_blocked_io()
        # 3) Possibly (re)dispatch a task to run
        self._preempt_if_needed()
        # 4) Run one tick of the currently running task, if any
        self._tick_running()
        # 5) Update waiting time (only tasks that are ready and have already arrived)
        self._update_waiting()
        # 6) Advance global time
        self.clock += 1
        # 7) Se a CPU estiver ociosa mas ainda houver trabalho (ready ou tasks_all),
        #    já faz uma nova admissão/escolha para o próximo tick.
        if self.running is None and (self.ready or self.tasks_all or self.blocked):
            self._admit_new_arrivals()
            self._update_blocked_io()
            self._preempt_if_needed()

    def run_full(self):
        # Continua enquanto houver tarefas não finalizadas em qualquer estado
        while self.tasks_all or self.ready or self.running is not None or self.blocked:
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
