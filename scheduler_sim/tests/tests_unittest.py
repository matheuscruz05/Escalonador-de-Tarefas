
import unittest
from scheduler_sim.scheduler.core import TCB, SimulationEngine
from scheduler_sim.scheduler.algorithms.fifo import FIFO
from scheduler_sim.scheduler.algorithms.srtf import SRTF
from scheduler_sim.scheduler.algorithms.priop import PRIOP

def build(tasks):
    return [TCB(pid=t[0], color="#333333", arrival=t[1], duration=t[2], priority=t[3]) for t in tasks]

class TestFCFS(unittest.TestCase):
    def test_basic_sequence(self):
        tasks = [("A",0,3,1), ("B",1,2,1), ("C",2,1,1)]
        eng = SimulationEngine(build(tasks), scheduler=FIFO(), quantum=2)
        eng.run_full()
        s = eng.summary()
        self.assertEqual((s["A"]["start"], s["A"]["finish"], s["A"]["waiting"]), (0,3,0))
        self.assertEqual((s["B"]["start"], s["B"]["finish"], s["B"]["waiting"]), (3,5,2))
        self.assertEqual((s["C"]["start"], s["C"]["finish"], s["C"]["waiting"]), (5,6,3))

class TestSRTF(unittest.TestCase):
    def test_preemption(self):
        tasks = [("P1",0,8,1), ("P2",1,4,1), ("P3",2,9,1)]
        eng = SimulationEngine(build(tasks), scheduler=SRTF(), quantum=2)
        eng.run_full()
        s = eng.summary()
        self.assertEqual((s["P2"]["finish"], s["P2"]["response"]), (5,0))
        self.assertEqual(s["P1"]["finish"], 12)
        self.assertEqual((s["P3"]["start"], s["P3"]["finish"]), (12,21))

class TestPRIOP(unittest.TestCase):
    def test_high_priority_preempts(self):
        tasks = [("L",0,5,1), ("H",1,2,5)]
        eng = SimulationEngine(build(tasks), scheduler=PRIOP(), quantum=2)
        eng.run_full()
        s = eng.summary()
        self.assertEqual((s["H"]["start"], s["H"]["finish"]), (1,3))
        self.assertEqual((s["L"]["start"], s["L"]["finish"]), (0,7))

if __name__ == "__main__":
    unittest.main()
