"""
SORTING FABRIC

Sorting that actually uses the Hollywood Squares message-passing architecture.

Each node:
- Holds one value in memory
- Receives EXEC messages with sorting opcodes
- Responds via EXEC_OK
- Updates its value

The sorting happens THROUGH THE BUS, not around it.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum

from .system import HSquaresOS
from .message import Message, MessageType, MessageFlags, exec_msg
from .node_kernel import NodeKernel, NodeStatus


class SortOp(IntEnum):
    """Sorting operation codes (used in EXEC payload)."""
    SET_VALUE = 0x40      # Set node's value
    GET_VALUE = 0x41      # Get node's value  
    SWAP_IF_GREATER = 0x45  # Swap if I'm greater


# Memory location for value storage
VALUE_ADDR = 0x0400


class SortingFabric:
    """
    Sorting that runs ON the Hollywood Squares fabric.
    
    Every operation is a message. Every comparison crosses the bus.
    You can step through it, trace it, replay it.
    """
    
    def __init__(self, os: HSquaresOS):
        self.os = os
        self.topology: Dict[int, List[int]] = {}  # node → [right_neighbors]
        
        # Install handlers on each worker
        for nid in range(1, os.num_workers + 1):
            self._install_handlers(os.workers[nid])
            # Initialize value to 0
            os.workers[nid].poke(VALUE_ADDR, 0)
        
        # Default: line topology (each node compares with next)
        self._setup_line()
        
        # Stats
        self.rounds = 0
        self.messages_sent = 0
    
    def _install_handlers(self, kernel: NodeKernel):
        """Install sorting operation handlers on a kernel."""
        
        def set_value_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """SET_VALUE: a = value to store."""
            kernel.poke(VALUE_ADDR, a)
            return (a, 0)
        
        def get_value_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """GET_VALUE: return current value."""
            my_val = kernel.peek(VALUE_ADDR)
            return (my_val, 0)
        
        def swap_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
            """SWAP_IF_GREATER: a = left neighbor's value. Swap if I'm smaller."""
            my_val = kernel.peek(VALUE_ADDR)
            left_val = a
            
            # For ascending sort: smaller values go left
            # If I'm smaller than my left neighbor, we swap
            if my_val < left_val:
                # I'm smaller, I take their (larger) value, they get mine
                kernel.poke(VALUE_ADDR, left_val)
                return (my_val, 1)  # Return my old (smaller) value, swapped=1
            return (my_val, 0)  # No swap
        
        # Register handlers
        kernel.register_handler(SortOp.SET_VALUE, set_value_handler)
        kernel.register_handler(SortOp.GET_VALUE, get_value_handler)
        kernel.register_handler(SortOp.SWAP_IF_GREATER, swap_handler)
    
    # ========== Topology ==========
    
    def _setup_line(self):
        """Line topology: each node compares with right neighbor."""
        self.topology = {}
        for i in range(1, self.os.num_workers):
            self.topology[i] = [i + 1]
        self.topology[self.os.num_workers] = []
    
    def _setup_ring(self):
        """Ring topology: line with wraparound."""
        self.topology = {}
        n = self.os.num_workers
        for i in range(1, n + 1):
            self.topology[i] = [i % n + 1]
    
    def _setup_grid(self, width: int = 0):
        """Grid topology: compare with right and down neighbors."""
        n = self.os.num_workers
        if width == 0:
            import math
            width = int(math.sqrt(n))
        
        self.topology = {}
        for i in range(1, n + 1):
            neighbors = []
            idx = i - 1
            col = idx % width
            row = idx // width
            
            # Right neighbor
            if col < width - 1 and i + 1 <= n:
                neighbors.append(i + 1)
            # Down neighbor
            if i + width <= n:
                neighbors.append(i + width)
            
            self.topology[i] = neighbors
    
    def set_topology(self, topo: str, **kwargs):
        """Set the network topology."""
        if topo == 'line':
            self._setup_line()
        elif topo == 'ring':
            self._setup_ring()
        elif topo == 'grid':
            self._setup_grid(**kwargs)
    
    # ========== Data Operations ==========
    
    def load(self, values: List[int]):
        """Load values into nodes via EXEC messages."""
        for i, val in enumerate(values[:self.os.num_workers], start=1):
            self._set_value(i, val)
    
    def read(self) -> List[int]:
        """Read values from all nodes via EXEC messages."""
        return [self._get_value(i) for i in range(1, self.os.num_workers + 1)]
    
    def _set_value(self, node: int, value: int):
        """Set a node's value via EXEC message."""
        result = self.os.exec(node, SortOp.SET_VALUE, value, 0)
        self.messages_sent += 1
    
    def _get_value(self, node: int) -> int:
        """Get a node's value via EXEC message."""
        result = self.os.exec(node, SortOp.GET_VALUE, 0, 0)
        self.messages_sent += 1
        if result:
            return result[0]
        # Fallback
        return self.os.workers[node].peek(VALUE_ADDR)
    
    # ========== Sorting ==========
    
    def bubble_step(self) -> int:
        """
        One bubble pass through the network.
        
        For each node, compare with right neighbor(s) and swap if needed.
        ALL THROUGH MESSAGES.
        
        Returns number of swaps.
        """
        swaps = 0
        
        # Phase 1: Odd-indexed nodes compare right (1,3,5,7)
        for i in range(1, self.os.num_workers + 1, 2):
            for neighbor in self.topology.get(i, []):
                if self._compare_swap(i, neighbor):
                    swaps += 1
        
        # Phase 2: Even-indexed nodes compare right (2,4,6,8)
        for i in range(2, self.os.num_workers + 1, 2):
            for neighbor in self.topology.get(i, []):
                if self._compare_swap(i, neighbor):
                    swaps += 1
        
        self.rounds += 1
        return swaps
    
    def _compare_swap(self, node_a: int, node_b: int) -> bool:
        """
        Compare two nodes via EXEC messages, swap if out of order.
        
        This is where the magic happens - sorting through the fabric.
        All through messages. All traceable. All deterministic.
        """
        # Get A's value via EXEC
        val_a = self._get_value(node_a)
        
        # Send SWAP_IF_GREATER to B via EXEC
        result = self.os.exec(node_b, SortOp.SWAP_IF_GREATER, val_a, 0)
        self.messages_sent += 1
        
        if result:
            old_b_val, swapped = result
            if swapped:
                # B took A's value, A needs B's old value
                self._set_value(node_a, old_b_val)
                return True
        
        return False
    
    def sort(self, max_rounds: int = 100) -> int:
        """Sort until stable."""
        self.rounds = 0
        self.messages_sent = 0
        
        for _ in range(max_rounds):
            swaps = self.bubble_step()
            if swaps == 0:
                break
        
        return self.rounds
    
    def sort_stepping(self, max_rounds: int = 100):
        """Generator that yields state after each step."""
        self.rounds = 0
        
        yield self._state()
        
        for _ in range(max_rounds):
            swaps = self.bubble_step()
            yield self._state()
            if swaps == 0:
                break
    
    def _state(self) -> Dict:
        """Get current state."""
        values = self.read()
        return {
            'round': self.rounds,
            'values': values,
            'sorted': self._is_sorted(values),
            'messages': self.messages_sent,
            'ticks': self.os.tick_count,
        }
    
    def _is_sorted(self, values: List[int]) -> bool:
        """Check if sorted."""
        return all(values[i] <= values[i+1] for i in range(len(values)-1))
    
    # ========== Display ==========
    
    def show(self) -> str:
        """Show current state."""
        values = self.read()
        lines = []
        
        status = 'SORTED' if self._is_sorted(values) else 'sorting...'
        lines.append(f"Round {self.rounds} | Msgs: {self.messages_sent} | {status}")
        lines.append("")
        
        max_val = max(values) if values else 1
        for i, v in enumerate(values, 1):
            bar = '█' * (v * 20 // max_val) if max_val > 0 else ''
            lines.append(f"n{i}: [{v:3d}] {bar}")
        
        return '\n'.join(lines)


def demo():
    """Demo sorting through the fabric."""
    print("=" * 60)
    print("SORTING FABRIC")
    print("Every comparison is a message. Every swap crosses the bus.")
    print("=" * 60)
    print()
    
    # Create system
    os = HSquaresOS(num_workers=8)
    os.boot()
    
    # Create sorting fabric
    fabric = SortingFabric(os)
    
    # Load data
    data = [64, 25, 12, 22, 11, 90, 42, 7]
    print("Loading via messages...")
    fabric.load(data)
    print(fabric.show())
    print()
    
    # Sort step by step
    print("Sorting via messages:")
    print("-" * 40)
    
    for state in fabric.sort_stepping():
        if state['round'] > 0:
            print(f"\nAfter round {state['round']} ({state['messages']} msgs):")
            print(fabric.show())
        if state['sorted']:
            break
    
    print()
    print("-" * 40)
    print(f"Sorted in {fabric.rounds} rounds")
    print(f"Total messages: {fabric.messages_sent}")
    print(f"Total ticks: {os.tick_count}")
    print()
    print("=" * 60)
    print("THE BUS IS THE COMPUTER")
    print("=" * 60)


if __name__ == '__main__':
    demo()
