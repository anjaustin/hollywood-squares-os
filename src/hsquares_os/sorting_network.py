"""
SORTING NETWORK

A sorting field built on Hollywood Squares.

"We don't speed up bubble sort by clever code — we change the space it lives in."

This demonstrates:
- Topology IS the algorithm
- Local rules, global behavior
- Parallel relaxation
- Deterministic, inspectable sorting
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from .system import HSquaresOS
from .message import Message, MessageType
from .node_kernel import NodeKernel, OpCode


# Custom message types for sorting
class SortOp:
    """Sorting operation codes."""
    STORE = 0x30      # Store value in node
    COMPARE = 0x31    # Compare with neighbor
    SWAP = 0x32       # Swap values
    GET = 0x33        # Get current value
    BUBBLE = 0x34     # One bubble step


@dataclass
class SortingNode:
    """A node in the sorting network."""
    node_id: int
    value: int = 0
    neighbors: List[int] = field(default_factory=list)  # Adjacent node IDs
    swapped: bool = False  # Did we swap this round?


class SortingNetwork:
    """
    A sorting network built on Hollywood Squares OS.
    
    Topology options:
    - LINE: 1D bubble sort (classic)
    - RING: 1D with wraparound
    - GRID: 2D bubble field
    - TORUS: 2D with wraparound
    
    Each node:
    - Holds one value
    - Compares with neighbors
    - Swaps if out of order
    - Repeats until quiescent
    """
    
    def __init__(self, os: HSquaresOS):
        self.os = os
        self.nodes: Dict[int, SortingNode] = {}
        self.topology = 'line'
        self.rounds = 0
        self.total_swaps = 0
        
        # Initialize sorting nodes for each worker
        for i in range(1, os.num_workers + 1):
            self.nodes[i] = SortingNode(node_id=i)
            # Register custom handler
            os.workers[i].register_handler(SortOp.BUBBLE, self._make_bubble_handler(i))
        
        # Default: line topology
        self._setup_line_topology()
    
    def _make_bubble_handler(self, node_id: int):
        """Create a bubble handler for a specific node."""
        def handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            # a = neighbor's value, b = direction (0=right, 1=down)
            # Returns: (my_value, swapped)
            node = self.nodes[node_id]
            my_val = node.value
            neighbor_val = a
            
            # Compare and maybe swap
            # For ascending sort: smaller values go left/up
            if b == 0:  # Comparing with right neighbor
                if my_val > neighbor_val:
                    # I'm bigger, I should go right - swap
                    node.value = neighbor_val
                    node.swapped = True
                    return (my_val, 1)  # Return my old value, swapped=1
            else:  # Comparing with bottom neighbor
                if my_val > neighbor_val:
                    node.value = neighbor_val
                    node.swapped = True
                    return (my_val, 1)
            
            return (my_val, 0)  # No swap
        
        return handler
    
    # ========== Topology Setup ==========
    
    def _setup_line_topology(self):
        """1D line: each node connected to left/right neighbors."""
        self.topology = 'line'
        n = len(self.nodes)
        for i in range(1, n + 1):
            neighbors = []
            if i > 1:
                neighbors.append(i - 1)  # Left
            if i < n:
                neighbors.append(i + 1)  # Right
            self.nodes[i].neighbors = neighbors
    
    def _setup_ring_topology(self):
        """1D ring: line with wraparound."""
        self.topology = 'ring'
        n = len(self.nodes)
        for i in range(1, n + 1):
            left = n if i == 1 else i - 1
            right = 1 if i == n else i + 1
            self.nodes[i].neighbors = [left, right]
    
    def _setup_grid_topology(self, width: int = 0):
        """2D grid: each node connected to up/down/left/right."""
        self.topology = 'grid'
        n = len(self.nodes)
        
        if width == 0:
            # Auto-detect square-ish grid
            import math
            width = int(math.sqrt(n))
            if width * width != n:
                width = n  # Fall back to line
        
        height = n // width
        
        for i in range(1, n + 1):
            idx = i - 1
            row = idx // width
            col = idx % width
            neighbors = []
            
            # Left
            if col > 0:
                neighbors.append(i - 1)
            # Right
            if col < width - 1:
                neighbors.append(i + 1)
            # Up
            if row > 0:
                neighbors.append(i - width)
            # Down
            if row < height - 1:
                neighbors.append(i + width)
            
            self.nodes[i].neighbors = neighbors
    
    def set_topology(self, topo: str, **kwargs):
        """Set the network topology."""
        if topo == 'line':
            self._setup_line_topology()
        elif topo == 'ring':
            self._setup_ring_topology()
        elif topo == 'grid':
            self._setup_grid_topology(**kwargs)
        else:
            raise ValueError(f"Unknown topology: {topo}")
    
    # ========== Data Loading ==========
    
    def load(self, values: List[int]):
        """Load values into the network."""
        for i, val in enumerate(values[:len(self.nodes)], start=1):
            self.nodes[i].value = val
            self.nodes[i].swapped = False
    
    def read(self) -> List[int]:
        """Read current values from network."""
        return [self.nodes[i].value for i in range(1, len(self.nodes) + 1)]
    
    # ========== Sorting Operations ==========
    
    def bubble_step(self) -> int:
        """
        Execute one bubble step across all nodes.
        
        Returns number of swaps performed.
        """
        swaps = 0
        
        # Reset swap flags
        for node in self.nodes.values():
            node.swapped = False
        
        # Even-odd transposition: parallel safe
        # Phase 1: Even nodes compare with right neighbor
        for i in range(1, len(self.nodes), 2):
            if i + 1 in self.nodes:
                swaps += self._compare_swap(i, i + 1)
        
        # Phase 2: Odd nodes compare with right neighbor
        for i in range(2, len(self.nodes), 2):
            if i + 1 in self.nodes:
                swaps += self._compare_swap(i, i + 1)
        
        self.rounds += 1
        self.total_swaps += swaps
        return swaps
    
    def _compare_swap(self, i: int, j: int) -> int:
        """Compare nodes i and j, swap if out of order. Returns 1 if swapped."""
        if self.nodes[i].value > self.nodes[j].value:
            # Swap
            self.nodes[i].value, self.nodes[j].value = \
                self.nodes[j].value, self.nodes[i].value
            self.nodes[i].swapped = True
            self.nodes[j].swapped = True
            return 1
        return 0
    
    def sort(self, max_rounds: int = 100) -> int:
        """
        Sort until quiescent (no swaps) or max_rounds.
        
        Returns total rounds needed.
        """
        self.rounds = 0
        self.total_swaps = 0
        
        for _ in range(max_rounds):
            swaps = self.bubble_step()
            if swaps == 0:
                break
        
        return self.rounds
    
    def sort_stepping(self, max_rounds: int = 100):
        """
        Generator that yields state after each step.
        
        For visualization/inspection.
        """
        self.rounds = 0
        self.total_swaps = 0
        
        yield self._state()
        
        for _ in range(max_rounds):
            swaps = self.bubble_step()
            yield self._state()
            if swaps == 0:
                break
    
    def _state(self) -> Dict:
        """Get current sorting state."""
        return {
            'round': self.rounds,
            'values': self.read(),
            'swapped': [self.nodes[i].swapped for i in range(1, len(self.nodes) + 1)],
            'total_swaps': self.total_swaps,
            'sorted': self._is_sorted(),
        }
    
    def _is_sorted(self) -> bool:
        """Check if values are sorted."""
        values = self.read()
        return all(values[i] <= values[i+1] for i in range(len(values)-1))
    
    # ========== Visualization ==========
    
    def show(self) -> str:
        """Show current state as ASCII."""
        values = self.read()
        swapped = [self.nodes[i].swapped for i in range(1, len(self.nodes) + 1)]
        
        # Bar chart
        max_val = max(values) if values else 1
        lines = []
        
        lines.append(f"Round {self.rounds} | Swaps: {self.total_swaps} | {'SORTED' if self._is_sorted() else 'sorting...'}")
        lines.append("")
        
        if self.topology == 'grid':
            # 2D display
            import math
            n = len(values)
            width = int(math.sqrt(n))
            if width * width < n:
                width += 1
            height = (n + width - 1) // width
            
            for row in range(height):
                row_vals = []
                for col in range(width):
                    idx = row * width + col
                    if idx < len(values):
                        v = values[idx]
                        s = '*' if swapped[idx] else ' '
                        row_vals.append(f"[{v:3d}{s}]")
                if row_vals:
                    lines.append(" ".join(row_vals))
        else:
            # 1D display with bars
            for i, (v, s) in enumerate(zip(values, swapped)):
                bar = '█' * (v * 20 // max_val) if max_val > 0 else ''
                swap_mark = '*' if s else ' '
                lines.append(f"n{i+1}: [{v:3d}]{swap_mark} {bar}")
        
        return '\n'.join(lines)
    
    def show_topology(self) -> str:
        """Show network topology."""
        lines = [f"Topology: {self.topology}"]
        lines.append("")
        
        for i in range(1, len(self.nodes) + 1):
            node = self.nodes[i]
            neighbors = ', '.join(f"n{n}" for n in node.neighbors)
            lines.append(f"n{i} [{node.value:3d}] → {neighbors}")
        
        return '\n'.join(lines)


def demo():
    """Demonstrate the sorting network."""
    print("=" * 60)
    print("SORTING NETWORK DEMO")
    print("The topology IS the algorithm")
    print("=" * 60)
    print()
    
    # Create system
    os = HSquaresOS(num_workers=8)
    os.boot()
    
    # Create sorting network
    net = SortingNetwork(os)
    
    # Load unsorted data
    data = [64, 25, 12, 22, 11, 90, 42, 7]
    net.load(data)
    
    print("Initial state:")
    print(net.show())
    print()
    
    # Sort with stepping
    print("Sorting (step by step):")
    print("-" * 40)
    
    for state in net.sort_stepping():
        if state['round'] > 0:
            print(f"\nAfter round {state['round']}:")
            print(net.show())
        if state['sorted']:
            break
    
    print()
    print("-" * 40)
    print(f"Sorted in {net.rounds} rounds with {net.total_swaps} swaps")
    print()
    
    # Show 2D grid
    print("=" * 60)
    print("2D GRID TOPOLOGY")
    print("=" * 60)
    print()
    
    # Create 4x2 grid (8 nodes)
    net.set_topology('grid', width=4)
    net.load([64, 25, 12, 22, 11, 90, 42, 7])
    
    print("Topology:")
    print(net.show_topology())
    print()
    
    print("Initial:")
    print(net.show())
    print()
    
    rounds = net.sort()
    print(f"\nSorted in {rounds} rounds")
    print(net.show())
    
    print()
    print("=" * 60)
    print("THE SPACE CARRIES THE ALGORITHM")
    print("=" * 60)


if __name__ == '__main__':
    demo()
