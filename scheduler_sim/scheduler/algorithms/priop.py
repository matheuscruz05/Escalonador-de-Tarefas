from typing import List, Optional
from ..core import TCB, Scheduler, _tie_key

class PRIOP(Scheduler):
    """Preemptive Priority. Higher numeric value => higher priority (positive scale).
       //Aging opcional: effective_priority = base + waiting_accum//aging_step (se aging_step>0).
       Aging opcional: effective_priority = base + floor(aging_wait/aging_step) (se aging_step>0).

    """
    def __init__(self, aging_step: int = 0):
        self.tiebreaker_order = ['arrival','pid']
        self.aging_step = max(0, int(aging_step))

    def set_tiebreaker(self, order):
        self.tiebreaker_order = list(order) if order else ['arrival','pid']

    def set_aging(self, step: int):
        self.aging_step = max(0, int(step))

    def _effective_priority(self, t: TCB) -> int:
        if self.aging_step > 0:
            # usa somente o tempo de espera desde que entrou na ready
            return t.priority + ( (getattr(t, "aging_wait", 0)) // self.aging_step )
        return t.priority
    
    def _tie_key_effective(self, t: TCB):
        """
        Constrói a chave de empate respeitando o contrato do tiebreaker,
        mas mapeando 'priority' para a prioridade *efetiva* quando o aging estiver ativo.
        Isso evita viés a favor da prioridade base em PRIOd.
        """
        key = []
        for f in self.tiebreaker_order:
            if f == "arrival":
                key.append(t.arrival)
            elif f == "pid":
                key.append(t.pid)
            elif f == "priority":
                # COM aging: usa prioridade efetiva; SEM aging: equivale à base
                key.append(self._effective_priority(t))
            else:
                key.append(None)
        return tuple(key)

    def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
        candidates: List[TCB] = list(ready)
        if running is not None:
            candidates.append(running)
        if not candidates:
            return None
        chosen = sorted(
            candidates,
            #key=lambda t: (-self._effective_priority(t),) + _tie_key(t, self.tiebreaker_order)
            # 1) maior prioridade *efetiva* primeiro
            # 2) depois desempates coerentes: se usuário incluiu 'priority' no tiebreaker,
            #    ela passa a refletir a prioridade *efetiva* quando aging>0
            key=lambda t: (-self._effective_priority(t),) + self._tie_key_effective(t)
        )[0]
        return chosen
