from typing import List, Optional
from ..core import TCB, Scheduler, _tie_key

class SRTF(Scheduler):
    """Shortest Remaining Time First (preemptive)."""
    def __init__(self):
        self.tiebreaker_order = ['arrival','pid']

    def set_tiebreaker(self, order):
        self.tiebreaker_order = list(order) if order else ['arrival','pid']

    def choose(self, ready: List[TCB], running: Optional[TCB], now: int) -> Optional[TCB]:
        candidates: List[TCB] = list(ready)
        if running is not None:
            candidates.append(running)
        if not candidates:
            return None
        chosen = sorted(candidates, key=lambda t: (t.remaining,) + _tie_key(t, self.tiebreaker_order))[0]
        return chosen
