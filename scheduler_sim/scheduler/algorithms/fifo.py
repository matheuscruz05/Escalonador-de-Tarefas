from typing import List, Optional
from ..core import TCB, Scheduler

class FIFO(Scheduler):
    """First-Come, First-Served (cooperativo).
    Mantém a ordem de chegada usando 'arrival_original' + 'enqueue_seq'.
    Nota: Ignora tiebreakers externos para manter estabilidade FIFO.
    """
    
    def __init__(self):
        pass
  
    def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
        # não preemptivo: se há alguém rodando, mantém
        if running is not None:
            return running
        if not ready:
            return None
        return min(ready, key=lambda t: (getattr(t, 'arrival_original', t.arrival),
                                          getattr(t, 'enqueue_seq', 0),
                                          t.pid))