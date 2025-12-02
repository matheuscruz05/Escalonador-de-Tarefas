from typing import List, Optional
from ..core import TCB, Scheduler

class FIFO(Scheduler):
    """First-Come, First-Served (cooperativo).
    Mantém a ordem de chegada usando 'arrival_original' + 'enqueue_seq'.
    Ignora tiebreakers externos para não poluir a política.
    """
    # def __init__(self):
    #     self.tiebreaker_order = ['arrival','pid']

    # def set_tiebreaker(self, order):
    #     self.tiebreaker_order = list(order) if order else ['arrival','pid']

    # def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
    #     if running is not None:
    #         return running
    #     if not ready:
    #         return None
    #     return sorted(ready, key=lambda t: _tie_key(t, self.tiebreaker_order))[0]
    
    def __init__(self):
        pass
  
    def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
        # não preemptivo: se há alguém rodando, mantém
        if running is not None:
            return running
        if not ready:
            return None
        # ANTES: dependia de sorted + tiebreaker externo, o que podia quebrar estabilidade
        # return sorted(ready, key=lambda t: _tie_key(t, ['arrival','pid']))[0]
        # AGORA: chave estável por construção
        return min(ready, key=lambda t: (getattr(t, 'arrival_original', t.arrival),
                                          getattr(t, 'enqueue_seq', 0),
                                          t.pid))