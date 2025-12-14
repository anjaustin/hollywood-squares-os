"""
BUBBLE MACHINE

A computational field that relaxes toward order.

Local rules + topology + phase scheduler + trace/replay.

This is the flagship demo of Hollywood Squares OS:
- Values drift toward ordered configuration via local compare-swap
- The topology determines the behavior
- Every step is traceable and replayable
- Structure is meaning

"It doesn't just sort — it flows."
"""

from typing import List, Dict, Tuple, Optional, Generator
from dataclasses import dataclass
from enum import IntEnum

from .system import HSquaresOS
from .node_kernel import NodeKernel


class BubbleOp(IntEnum):
    """Bubble Machine operations."""
    GET = 0x20       # Get node's value
    SET = 0x21       # Set node's value
    CSWAP = 0x22     # Compare-swap with neighbor value


class Direction(IntEnum):
    """Swap direction."""
    ASC = 0   # Smaller goes left/up
    DESC = 1  # Larger goes left/up


# Memory addresses
VALUE_ADDR = 0x0400
CHANGED_ADDR = 0x0401


@dataclass
class Phase:
    """A phase in the bubble schedule."""
    name: str
    pairs: List[Tuple[int, int]]


@dataclass 
class BubbleEvent:
    """A single bubble event for tracing."""
    tick: int
    phase: str
    node_a: int
    node_b: int
    val_a: int
    val_b: int
    swapped: bool
    new_a: int
    new_b: int


class BubbleMachine:
    """
    The Bubble Machine.
    
    A computational field where values relax toward order
    through local compare-swap operations.
    
    The topology IS the algorithm.
    The messages carry the computation.
    The trace tells the story.
    """
    
    def __init__(self, os: HSquaresOS):
        self.os = os
        self.topology = 'line'
        self.direction = Direction.ASC
        
        # Phase schedule (set by topology)
        self.phases: List[Phase] = []
        
        # Event log
        self.events: List[BubbleEvent] = []
        self.total_swaps = 0
        self.cycles = 0
        
        # Install handlers
        for nid in range(1, os.num_workers + 1):
            self._install_handlers(os.workers[nid])
        
        # Default topology
        self._setup_line()
    
    def _install_handlers(self, kernel: NodeKernel):
        """Install bubble operations on a kernel."""
        
        def get_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """GET: return current value."""
            return (kernel.peek(VALUE_ADDR), 0)
        
        def set_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """SET: store value."""
            kernel.poke(VALUE_ADDR, a)
            kernel.poke(CHANGED_ADDR, 1)
            return (a, 0)
        
        def cswap_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """
            CSWAP: Compare-swap with neighbor.
            
            a = neighbor's value
            b = direction (ASC=0, DESC=1)
            
            Returns (my_new_value, swapped)
            """
            my_val = kernel.peek(VALUE_ADDR)
            neighbor_val = a
            direction = b
            
            should_swap = False
            if direction == Direction.ASC:
                # Ascending: smaller values go left
                # If I'm right node and smaller, swap
                should_swap = my_val < neighbor_val
            else:
                # Descending: larger values go left
                should_swap = my_val > neighbor_val
            
            if should_swap:
                kernel.poke(VALUE_ADDR, neighbor_val)
                kernel.poke(CHANGED_ADDR, 1)
                return (my_val, 1)  # Return my old value, swapped=1
            
            return (my_val, 0)
        
        kernel.register_handler(BubbleOp.GET, get_handler)
        kernel.register_handler(BubbleOp.SET, set_handler)
        kernel.register_handler(BubbleOp.CSWAP, cswap_handler)
    
    # ========== Topology ==========
    
    def _setup_line(self):
        """Line topology: odd-even transposition."""
        self.topology = 'line'
        n = self.os.num_workers
        
        # Even phase: pairs (1,2), (3,4), (5,6), (7,8)
        even_pairs = [(i, i+1) for i in range(1, n, 2) if i+1 <= n]
        
        # Odd phase: pairs (2,3), (4,5), (6,7)
        odd_pairs = [(i, i+1) for i in range(2, n, 2) if i+1 <= n]
        
        self.phases = [
            Phase('EVEN', even_pairs),
            Phase('ODD', odd_pairs),
        ]
    
    def _setup_ring(self):
        """Ring topology: line with wraparound."""
        self.topology = 'ring'
        n = self.os.num_workers
        
        even_pairs = [(i, i+1) for i in range(1, n, 2) if i+1 <= n]
        odd_pairs = [(i, (i % n) + 1) for i in range(2, n+1, 2)]
        
        self.phases = [
            Phase('EVEN', even_pairs),
            Phase('ODD', odd_pairs),
        ]
    
    def _setup_grid(self, width: int = 0):
        """
        Grid topology: 4-phase checkerboard.
        
        H-even, H-odd, V-even, V-odd
        """
        self.topology = 'grid'
        n = self.os.num_workers
        
        if width == 0:
            import math
            width = int(math.sqrt(n))
        
        height = (n + width - 1) // width
        
        # Horizontal phases
        h_even = []
        h_odd = []
        for row in range(height):
            for col in range(0, width - 1, 2):
                a = row * width + col + 1
                b = a + 1
                if a <= n and b <= n:
                    h_even.append((a, b))
            for col in range(1, width - 1, 2):
                a = row * width + col + 1
                b = a + 1
                if a <= n and b <= n:
                    h_odd.append((a, b))
        
        # Vertical phases
        v_even = []
        v_odd = []
        for col in range(width):
            for row in range(0, height - 1, 2):
                a = row * width + col + 1
                b = a + width
                if a <= n and b <= n:
                    v_even.append((a, b))
            for row in range(1, height - 1, 2):
                a = row * width + col + 1
                b = a + width
                if a <= n and b <= n:
                    v_odd.append((a, b))
        
        self.phases = [
            Phase('H-EVEN', h_even),
            Phase('H-ODD', h_odd),
            Phase('V-EVEN', v_even),
            Phase('V-ODD', v_odd),
        ]
    
    def set_topology(self, topo: str, **kwargs):
        """Set the bubble field topology."""
        if topo == 'line':
            self._setup_line()
        elif topo == 'ring':
            self._setup_ring()
        elif topo == 'grid':
            self._setup_grid(**kwargs)
        else:
            raise ValueError(f"Unknown topology: {topo}")
    
    # ========== Data ==========
    
    def load(self, values: List[int]):
        """Load values into the field."""
        for i, val in enumerate(values[:self.os.num_workers], start=1):
            self.os.exec(i, BubbleOp.SET, val & 0xFF, 0)
        self.events.clear()
        self.total_swaps = 0
        self.cycles = 0
    
    def load_random(self, seed: int = None):
        """Load random values."""
        import random
        if seed is not None:
            random.seed(seed)
        values = [random.randint(0, 255) for _ in range(self.os.num_workers)]
        self.load(values)
    
    def read(self) -> List[int]:
        """Read current field values."""
        values = []
        for i in range(1, self.os.num_workers + 1):
            result = self.os.exec(i, BubbleOp.GET, 0, 0)
            values.append(result[0] if result else 0)
        return values
    
    # ========== Execution ==========
    
    def step(self) -> int:
        """
        Execute one complete cycle (all phases).
        
        Returns number of swaps.
        """
        cycle_swaps = 0
        
        for phase in self.phases:
            phase_swaps = self._run_phase(phase)
            cycle_swaps += phase_swaps
        
        self.cycles += 1
        self.total_swaps += cycle_swaps
        return cycle_swaps
    
    def step_phase(self) -> Tuple[str, int]:
        """
        Execute one phase only.
        
        Returns (phase_name, swaps).
        """
        phase_idx = self.cycles % len(self.phases)
        phase = self.phases[phase_idx]
        swaps = self._run_phase(phase)
        
        if phase_idx == len(self.phases) - 1:
            self.cycles += 1
        
        self.total_swaps += swaps
        return (phase.name, swaps)
    
    def _run_phase(self, phase: Phase) -> int:
        """Execute a single phase, return swap count."""
        swaps = 0
        
        for (a, b) in phase.pairs:
            swapped = self._compare_swap(a, b, phase.name)
            if swapped:
                swaps += 1
        
        return swaps
    
    def _compare_swap(self, node_a: int, node_b: int, phase_name: str) -> bool:
        """Compare-swap two nodes, log the event."""
        # Get values
        result_a = self.os.exec(node_a, BubbleOp.GET, 0, 0)
        result_b = self.os.exec(node_b, BubbleOp.GET, 0, 0)
        
        val_a = result_a[0] if result_a else 0
        val_b = result_b[0] if result_b else 0
        
        # Send CSWAP to node_b with node_a's value
        result = self.os.exec(node_b, BubbleOp.CSWAP, val_a, self.direction)
        
        swapped = False
        new_a, new_b = val_a, val_b
        
        if result and result[1]:  # swapped
            old_b = result[0]
            # B took A's value, A gets B's old value
            self.os.exec(node_a, BubbleOp.SET, old_b, 0)
            new_a, new_b = old_b, val_a
            swapped = True
        
        # Log event
        event = BubbleEvent(
            tick=self.os.tick_count,
            phase=phase_name,
            node_a=node_a,
            node_b=node_b,
            val_a=val_a,
            val_b=val_b,
            swapped=swapped,
            new_a=new_a,
            new_b=new_b,
        )
        self.events.append(event)
        
        return swapped
    
    def run(self, max_cycles: int = 100) -> int:
        """Run until quiescence or max_cycles."""
        for _ in range(max_cycles):
            swaps = self.step()
            if swaps == 0:
                break
        return self.cycles
    
    def run_stepping(self, max_cycles: int = 100) -> Generator:
        """Generator that yields state after each cycle."""
        yield self._state()
        
        for _ in range(max_cycles):
            swaps = self.step()
            yield self._state()
            if swaps == 0:
                break
    
    def _state(self) -> Dict:
        """Get current state."""
        values = self.read()
        return {
            'cycle': self.cycles,
            'values': values,
            'sorted': self._is_sorted(values),
            'swaps': self.total_swaps,
            'events': len(self.events),
        }
    
    def _is_sorted(self, values: List[int]) -> bool:
        """Check if field is sorted."""
        if self.direction == Direction.ASC:
            return all(values[i] <= values[i+1] for i in range(len(values)-1))
        else:
            return all(values[i] >= values[i+1] for i in range(len(values)-1))
    
    # ========== Display ==========
    
    def show(self) -> str:
        """Show current field state."""
        values = self.read()
        lines = []
        
        status = 'SETTLED' if self._is_sorted(values) else 'flowing...'
        lines.append(f"Cycle {self.cycles} | Swaps: {self.total_swaps} | {status}")
        lines.append(f"Topology: {self.topology} | Direction: {'ASC' if self.direction == Direction.ASC else 'DESC'}")
        lines.append("")
        
        max_val = max(values) if values else 1
        
        if self.topology == 'grid':
            import math
            width = int(math.sqrt(len(values)))
            if width * width < len(values):
                width += 1
            
            for row in range((len(values) + width - 1) // width):
                row_vals = []
                for col in range(width):
                    idx = row * width + col
                    if idx < len(values):
                        row_vals.append(f"[{values[idx]:3d}]")
                if row_vals:
                    lines.append(" ".join(row_vals))
        else:
            for i, v in enumerate(values, 1):
                bar = '█' * (v * 20 // max_val) if max_val > 0 else ''
                lines.append(f"n{i}: [{v:3d}] {bar}")
        
        return '\n'.join(lines)
    
    def show_trace(self, last_n: int = 20) -> str:
        """Show recent events."""
        lines = []
        for event in self.events[-last_n:]:
            swap_str = f"{event.val_a}<->{event.val_b} => ({event.new_a},{event.new_b})" if event.swapped else f"{event.val_a}<=>{event.val_b} (no swap)"
            lines.append(f"[t={event.tick:4d}] {event.phase:<8} pair(n{event.node_a},n{event.node_b}) {swap_str}")
        return '\n'.join(lines)
    
    def show_phases(self) -> str:
        """Show phase schedule."""
        lines = [f"Topology: {self.topology}", ""]
        for phase in self.phases:
            pairs_str = " ".join(f"({a},{b})" for a, b in phase.pairs)
            lines.append(f"{phase.name}: {pairs_str}")
        return '\n'.join(lines)


def demo():
    """Demonstrate the Bubble Machine."""
    print("=" * 60)
    print("BUBBLE MACHINE")
    print("A computational field that relaxes toward order")
    print("=" * 60)
    print()
    
    # Create system
    os = HSquaresOS(num_workers=8)
    os.boot()
    
    # Create bubble machine
    bubble = BubbleMachine(os)
    
    # Load random values
    bubble.load([64, 25, 12, 22, 11, 90, 42, 7])
    
    print("Initial state:")
    print(bubble.show())
    print()
    
    print("Phase schedule:")
    print(bubble.show_phases())
    print()
    
    # Run with stepping
    print("Running...")
    print("-" * 40)
    
    for state in bubble.run_stepping():
        if state['cycle'] > 0:
            print(f"\nCycle {state['cycle']}:")
            print(bubble.show())
        if state['sorted']:
            break
    
    print()
    print("-" * 40)
    print(f"Settled in {bubble.cycles} cycles")
    print(f"Total swaps: {bubble.total_swaps}")
    print(f"Total events: {len(bubble.events)}")
    print()
    
    print("Event trace (last 10):")
    print(bubble.show_trace(10))
    print()
    
    print("=" * 60)
    print("THE FIELD RELAXES. STRUCTURE IS MEANING.")
    print("=" * 60)


if __name__ == '__main__':
    demo()
