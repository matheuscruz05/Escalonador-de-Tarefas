from typing import List, Optional
from ..core import TCB, Scheduler

class PRIOP(Scheduler):
    """
    Priority Preemptive Scheduling com aging opcional.
        
    Características:
    - Prioridade numérica mais alta = maior prioridade
    - Aging: incrementa prioridade com tempo de espera
    - Preemptivo: pode interromper tarefas de menor prioridade
    
    Args:
        aging_step: Incremento de prioridade a cada N ticks de espera
                (0 = aging desabilitado, default)
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
            effective = t.priority + ( t.aging_wait // self.aging_step )
            return effective
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
        """Seleciona tarefa com maior prioridade efetiva (com aging se habilitado)."""
        candidates: List[TCB] = list(ready)
        if running is not None:
            candidates.append(running)
        if not candidates:
            return None
        chosen = sorted(
            candidates,
            key=lambda t: (-self._effective_priority(t),) + self._tie_key_effective(t)
        )[0]
        return chosen
