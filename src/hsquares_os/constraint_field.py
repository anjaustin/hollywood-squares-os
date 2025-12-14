"""
CONSTRAINT FIELD

A distributed CSP engine where computation is relaxation.

Each node = a variable (Sudoku cell)
Each node stores a domain (bitset of possible values)
Edges = constraints (row, col, box)
Computation = eliminate impossible values until fixed point

"This system doesn't search for solutions. It relaxes toward them."

You can watch a problem think.
"""

from typing import List, Dict, Set, Tuple, Optional, Generator
from dataclasses import dataclass, field
from enum import IntEnum
import copy

from .system import HSquaresOS
from .node_kernel import NodeKernel


class ConstraintOp(IntEnum):
    """Constraint field operations."""
    DOMAIN_GET = 0x30      # Get current domain
    DOMAIN_SET = 0x31      # Set domain (initialize)
    DOMAIN_DELTA = 0x32    # Remove values from domain
    DOMAIN_FULL = 0x33     # Get full domain as two bytes
    IS_SINGLETON = 0x34    # Check if single value
    GET_VALUE = 0x35       # Get singleton value (0 if not singleton)


# Memory addresses for cell state
DOMAIN_LO_ADDR = 0x0400   # Lower 8 bits of domain
DOMAIN_HI_ADDR = 0x0401   # Upper bit (value 9)
DIRTY_ADDR = 0x0402       # Dirty flag


@dataclass
class PropagationEvent:
    """A single propagation event for tracing."""
    tick: int
    cell: Tuple[int, int]  # (row, col)
    event_type: str        # 'eliminated', 'singleton', 'contradiction'
    values: Set[int]       # Values involved
    reason: str            # Why this happened
    domain_before: Set[int]
    domain_after: Set[int]


@dataclass
class CellState:
    """State of a single cell (for tracking outside the nodes)."""
    row: int
    col: int
    node_id: int
    domain: Set[int]       # Possible values {1-9}
    fixed: Optional[int] = None  # If singleton, the value
    
    @property
    def entropy(self) -> int:
        return len(self.domain)
    
    @property
    def is_singleton(self) -> bool:
        return len(self.domain) == 1
    
    @property
    def is_contradiction(self) -> bool:
        return len(self.domain) == 0


class ConstraintField:
    """
    A Sudoku constraint propagation field.
    
    81 cells, each a node in the field.
    Constraints: row, column, box (each cell has 20 neighbors).
    Relaxation: eliminate values until fixed point.
    
    For the demo, we use a subset (e.g., 9 cells = one row/col/box)
    to fit in 8 workers. Full 81-cell version requires more nodes.
    """
    
    def __init__(self, os: HSquaresOS, size: int = 9):
        """
        Initialize constraint field.
        
        For 8-worker demo: size=3 (3x3 = 9 cells, but we only use 8)
        For full Sudoku: size=9 (81 cells, needs 81 workers)
        """
        self.os = os
        self.size = min(size, os.num_workers)  # Limit to available workers
        
        # Cell state tracking
        self.cells: Dict[int, CellState] = {}
        
        # Constraint graph: cell_id -> set of neighbor cell_ids
        self.neighbors: Dict[int, Set[int]] = {}
        
        # Event log
        self.events: List[PropagationEvent] = []
        self.ticks = 0
        self.total_eliminations = 0
        
        # Install handlers
        for nid in range(1, os.num_workers + 1):
            self._install_handlers(os.workers[nid])
        
        # Setup cells and constraints
        self._setup_cells()
        self._setup_constraints()
    
    def _install_handlers(self, kernel: NodeKernel):
        """Install constraint handlers on a kernel."""
        
        def domain_get(a: int, b: int, flags: int) -> Tuple[int, int]:
            """Return domain as (lo, hi) bytes."""
            lo = kernel.peek(DOMAIN_LO_ADDR)
            hi = kernel.peek(DOMAIN_HI_ADDR)
            return (lo, hi)
        
        def domain_set(a: int, b: int, flags: int) -> Tuple[int, int]:
            """Set domain from (lo, hi) bytes."""
            kernel.poke(DOMAIN_LO_ADDR, a)
            kernel.poke(DOMAIN_HI_ADDR, b & 0x01)
            kernel.poke(DIRTY_ADDR, 1)
            return (a, b)
        
        def domain_delta(a: int, b: int, flags: int) -> Tuple[int, int]:
            """Remove values from domain. a=lo_mask, b=hi_mask.
            
            Returns (changed_flag, new_entropy) where:
            - changed_flag: 1 if domain changed, 0 otherwise
            - new_entropy: number of remaining values in domain
            """
            lo = kernel.peek(DOMAIN_LO_ADDR)
            hi = kernel.peek(DOMAIN_HI_ADDR)
            
            old_lo, old_hi = lo, hi
            lo = lo & ~a  # Remove bits in mask
            hi = hi & ~b
            
            kernel.poke(DOMAIN_LO_ADDR, lo)
            kernel.poke(DOMAIN_HI_ADDR, hi)
            
            # Check if changed
            changed = (lo != old_lo) or (hi != old_hi)
            if changed:
                kernel.poke(DIRTY_ADDR, 1)
            
            # Count remaining bits (entropy)
            domain = lo | (hi << 8)
            entropy = bin(domain).count('1')
            
            # Return changed flag and entropy (both fit in one byte)
            return (1 if changed else 0, entropy)
        
        def is_singleton(a: int, b: int, flags: int) -> Tuple[int, int]:
            """Check if domain has exactly one value."""
            lo = kernel.peek(DOMAIN_LO_ADDR)
            hi = kernel.peek(DOMAIN_HI_ADDR)
            domain = lo | (hi << 8)
            
            # Count bits
            count = bin(domain).count('1')
            return (1 if count == 1 else 0, count)
        
        def get_value(a: int, b: int, flags: int) -> Tuple[int, int]:
            """Get singleton value (1-9) or 0 if not singleton."""
            lo = kernel.peek(DOMAIN_LO_ADDR)
            hi = kernel.peek(DOMAIN_HI_ADDR)
            domain = lo | (hi << 8)
            
            count = bin(domain).count('1')
            if count != 1:
                return (0, count)
            
            # Find the set bit (value 1-9)
            for v in range(1, 10):
                if domain & (1 << (v - 1)):
                    return (v, 1)
            return (0, 0)
        
        kernel.register_handler(ConstraintOp.DOMAIN_GET, domain_get)
        kernel.register_handler(ConstraintOp.DOMAIN_SET, domain_set)
        kernel.register_handler(ConstraintOp.DOMAIN_DELTA, domain_delta)
        kernel.register_handler(ConstraintOp.IS_SINGLETON, is_singleton)
        kernel.register_handler(ConstraintOp.GET_VALUE, get_value)
    
    def _setup_cells(self):
        """Setup cells for available workers."""
        # Map node IDs to cells
        # For 8 workers: use a 1D layout (like one row of Sudoku)
        for nid in range(1, self.os.num_workers + 1):
            row = (nid - 1) // 3
            col = (nid - 1) % 3
            
            self.cells[nid] = CellState(
                row=row,
                col=col,
                node_id=nid,
                domain=set(range(1, 10)),  # {1-9}
            )
    
    def _setup_constraints(self):
        """Setup constraint graph (neighbors)."""
        # For simplified demo: all cells constrain each other (all-different)
        for nid in self.cells:
            self.neighbors[nid] = set()
            for other_nid in self.cells:
                if other_nid != nid:
                    self.neighbors[nid].add(other_nid)
    
    def _domain_to_bitset(self, domain: Set[int]) -> Tuple[int, int]:
        """Convert domain set to (lo, hi) bytes."""
        bits = 0
        for v in domain:
            if 1 <= v <= 9:
                bits |= (1 << (v - 1))
        return (bits & 0xFF, (bits >> 8) & 0x01)
    
    def _bitset_to_domain(self, lo: int, hi: int) -> Set[int]:
        """Convert (lo, hi) bytes to domain set."""
        bits = lo | (hi << 8)
        return {v for v in range(1, 10) if bits & (1 << (v - 1))}
    
    # ========== Data Operations ==========
    
    def load_puzzle(self, givens: Dict[int, int]):
        """
        Load a puzzle with given values.
        
        givens: {node_id: value} for fixed cells
        """
        self.events.clear()
        self.ticks = 0
        self.total_eliminations = 0
        
        # Reset all cells to full domain
        for nid in self.cells:
            self._set_domain(nid, set(range(1, 10)))
            self.cells[nid].fixed = None
        
        # Set givens (this triggers initial propagation tracking)
        for nid, value in givens.items():
            if nid in self.cells:
                cell = self.cells[nid]
                before = cell.domain.copy()
                self._set_domain(nid, {value})
                cell.fixed = value
                
                # Log the given as an event
                event = PropagationEvent(
                    tick=0,
                    cell=(cell.row, cell.col),
                    event_type='singleton',
                    values={value},
                    reason='given',
                    domain_before=before,
                    domain_after={value},
                )
                self.events.append(event)
    
    def load_row(self, values: List[int]):
        """
        Load a row of values (0 = empty).
        
        Convenience for 8-worker demo.
        """
        givens = {}
        for i, v in enumerate(values[:self.os.num_workers], start=1):
            if v > 0:
                givens[i] = v
        self.load_puzzle(givens)
    
    def _set_domain(self, node_id: int, domain: Set[int]):
        """Set a cell's domain."""
        lo, hi = self._domain_to_bitset(domain)
        self.os.exec(node_id, ConstraintOp.DOMAIN_SET, lo, hi)
        self.cells[node_id].domain = domain.copy()
        if len(domain) == 1:
            self.cells[node_id].fixed = list(domain)[0]
    
    def _get_domain(self, node_id: int) -> Set[int]:
        """Get a cell's current domain."""
        result = self.os.exec(node_id, ConstraintOp.DOMAIN_GET, 0, 0)
        if result:
            return self._bitset_to_domain(result[0], result[1])
        return set()
    
    def _eliminate(self, node_id: int, values: Set[int], reason: str) -> bool:
        """
        Eliminate values from a cell's domain.
        
        Returns True if domain changed.
        """
        # Get current domain
        before = self._get_domain(node_id)
        
        # Create removal mask
        lo_mask, hi_mask = self._domain_to_bitset(values)
        
        # Send delta - returns (changed_flag, new_entropy)
        result = self.os.exec(node_id, ConstraintOp.DOMAIN_DELTA, lo_mask, hi_mask)
        
        # Result is (changed_flag, new_entropy)
        changed = result[0] if result else 0
        
        if changed:
            after = self._get_domain(node_id)
            self.cells[node_id].domain = after
            
            # Check if became singleton
            if len(after) == 1:
                self.cells[node_id].fixed = list(after)[0]
            
            # Log event
            cell = self.cells[node_id]
            event = PropagationEvent(
                tick=self.os.tick_count,
                cell=(cell.row, cell.col),
                event_type='singleton' if len(after) == 1 else 'eliminated',
                values=values & before,  # Actually removed
                reason=reason,
                domain_before=before,
                domain_after=after,
            )
            self.events.append(event)
            self.total_eliminations += len(values & before)
            
            # Check for contradiction
            if len(after) == 0:
                event.event_type = 'contradiction'
            
            return True
        
        return False
    
    # ========== Propagation ==========
    
    def propagate_step(self) -> int:
        """
        Execute one propagation step.
        
        For each singleton, eliminate its value from neighbors.
        
        Returns number of eliminations.
        """
        eliminations = 0
        
        # First, sync all domains from nodes to local state
        for nid in self.cells:
            self.cells[nid].domain = self._get_domain(nid)
            if len(self.cells[nid].domain) == 1:
                self.cells[nid].fixed = list(self.cells[nid].domain)[0]
        
        # Find all singletons
        singletons = []
        for nid, cell in self.cells.items():
            if cell.is_singleton and cell.fixed:
                singletons.append((nid, cell.fixed))
        
        # Propagate each singleton to its neighbors
        for nid, value in singletons:
            cell = self.cells[nid]
            
            for neighbor_id in self.neighbors.get(nid, []):
                neighbor = self.cells.get(neighbor_id)
                # Re-sync neighbor domain before checking
                neighbor.domain = self._get_domain(neighbor_id)
                
                if neighbor and not neighbor.is_singleton and value in neighbor.domain:
                    reason = f"cell({cell.row},{cell.col})={value}"
                    if self._eliminate(neighbor_id, {value}, reason):
                        eliminations += 1
        
        self.ticks += 1
        return eliminations
    
    def propagate(self, max_steps: int = 100) -> int:
        """
        Propagate until fixed point or max_steps.
        
        Returns total steps taken.
        """
        for step in range(max_steps):
            elims = self.propagate_step()
            if elims == 0:
                break
        return self.ticks
    
    def propagate_stepping(self, max_steps: int = 100) -> Generator:
        """Generator that yields state after each step."""
        yield self._state()
        
        for _ in range(max_steps):
            elims = self.propagate_step()
            yield self._state()
            if elims == 0:
                break
    
    def _state(self) -> Dict:
        """Get current state."""
        # Sync domains from nodes
        for nid in self.cells:
            self.cells[nid].domain = self._get_domain(nid)
        
        solved_count = sum(1 for c in self.cells.values() if c.is_singleton)
        contradiction = any(c.is_contradiction for c in self.cells.values())
        
        return {
            'tick': self.ticks,
            'solved': solved_count,
            'total': len(self.cells),
            'eliminations': self.total_eliminations,
            'events': len(self.events),
            'contradiction': contradiction,
            'quiescent': solved_count == len(self.cells) or contradiction,
        }
    
    # ========== Display ==========
    
    def show(self) -> str:
        """Show current field state."""
        lines = []
        
        # Sync domains
        for nid in self.cells:
            self.cells[nid].domain = self._get_domain(nid)
        
        solved = sum(1 for c in self.cells.values() if c.is_singleton)
        lines.append(f"Tick {self.ticks} | Solved: {solved}/{len(self.cells)} | Eliminations: {self.total_eliminations}")
        lines.append("")
        
        # Show each cell
        for nid in sorted(self.cells.keys()):
            cell = self.cells[nid]
            if cell.is_singleton:
                domain_str = f"[{cell.fixed}]"
                status = "FIXED"
            elif cell.is_contradiction:
                domain_str = "[X]"
                status = "CONTRADICTION"
            else:
                domain_str = "{" + ",".join(str(v) for v in sorted(cell.domain)) + "}"
                status = f"entropy={cell.entropy}"
            
            lines.append(f"n{nid} ({cell.row},{cell.col}): {domain_str:<20} {status}")
        
        return '\n'.join(lines)
    
    def show_grid(self) -> str:
        """Show as a grid (for visual display)."""
        lines = []
        
        # Sync domains
        for nid in self.cells:
            self.cells[nid].domain = self._get_domain(nid)
        
        lines.append(f"Tick {self.ticks}")
        lines.append("")
        
        # Build grid
        row_cells = {}
        for cell in self.cells.values():
            if cell.row not in row_cells:
                row_cells[cell.row] = {}
            row_cells[cell.row][cell.col] = cell
        
        for row in sorted(row_cells.keys()):
            row_str = ""
            for col in sorted(row_cells[row].keys()):
                cell = row_cells[row][col]
                if cell.is_singleton:
                    row_str += f" {cell.fixed} "
                elif cell.is_contradiction:
                    row_str += " X "
                else:
                    row_str += " . "
            lines.append(row_str)
        
        return '\n'.join(lines)
    
    def show_trace(self, last_n: int = 20) -> str:
        """Show recent propagation events."""
        lines = []
        for event in self.events[-last_n:]:
            values_str = ",".join(str(v) for v in sorted(event.values))
            if event.event_type == 'singleton':
                lines.append(f"[t={event.tick:4d}] cell({event.cell[0]},{event.cell[1]}): FIXED = {list(event.domain_after)[0]}")
            elif event.event_type == 'contradiction':
                lines.append(f"[t={event.tick:4d}] cell({event.cell[0]},{event.cell[1]}): CONTRADICTION!")
            else:
                lines.append(f"[t={event.tick:4d}] cell({event.cell[0]},{event.cell[1]}): eliminated {{{values_str}}} via {event.reason}")
        return '\n'.join(lines)
    
    def why(self, node_id: int) -> str:
        """Explain how a cell got its current state."""
        cell = self.cells.get(node_id)
        if not cell:
            return f"Unknown cell: {node_id}"
        
        lines = [f"Cell ({cell.row},{cell.col}) - node {node_id}"]
        lines.append(f"Current domain: {sorted(cell.domain)}")
        lines.append("")
        lines.append("History:")
        
        # Find all events for this cell
        cell_events = [e for e in self.events if e.cell == (cell.row, cell.col)]
        
        if not cell_events:
            lines.append("  (no eliminations recorded)")
        else:
            for event in cell_events:
                values_str = ",".join(str(v) for v in sorted(event.values))
                lines.append(f"  [t={event.tick}] removed {{{values_str}}} via {event.reason}")
        
        return '\n'.join(lines)


def demo():
    """Demonstrate the Constraint Field."""
    print("=" * 60)
    print("CONSTRAINT FIELD")
    print("Watch a problem think.")
    print("=" * 60)
    print()
    
    # Create system
    os = HSquaresOS(num_workers=8)
    os.boot()
    print(f"System booted: 8 workers online")
    print()
    
    # Create constraint field
    field = ConstraintField(os)
    
    # Load puzzle: 8 cells with all-different constraint
    # Givens strategically placed to cascade
    print("=" * 60)
    print("PUZZLE: 8-cell all-different constraint")
    print("=" * 60)
    print()
    print("Cells 1-8 must all have different values (1-9).")
    print()
    print("Givens:")
    print("  Cell 1 = 3")
    print("  Cell 3 = 5") 
    print("  Cell 5 = 8")
    print("  Cell 7 = 2")
    print()
    
    field.load_puzzle({1: 3, 3: 5, 5: 8, 7: 2})
    
    print("Initial state:")
    print(field.show())
    print()
    
    # Propagate with stepping
    print("=" * 60)
    print("PROPAGATION")
    print("=" * 60)
    
    for state in field.propagate_stepping(max_steps=10):
        if state['tick'] > 0:
            print(f"\n--- Tick {state['tick']} ---")
            print(field.show())
        if state['quiescent']:
            print("\n*** QUIESCENT: Fixed point reached ***")
            break
    
    print()
    print("=" * 60)
    print("EVENT TRACE")
    print("=" * 60)
    print()
    print(field.show_trace(20))
    print()
    
    # Explain cells
    print("=" * 60)
    print("EXPLANATIONS")
    print("=" * 60)
    print()
    print("WHY cell 2?")
    print("-" * 40)
    print(field.why(2))
    print()
    print("WHY cell 4?")
    print("-" * 40)
    print(field.why(4))
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    print(f"Ticks:        {field.ticks}")
    print(f"Eliminations: {field.total_eliminations}")
    print(f"Events:       {len(field.events)}")
    print(f"Messages:     {os.bus.delivered}")
    print()
    
    # Show final state compactly
    values = []
    for nid in sorted(field.cells.keys()):
        cell = field.cells[nid]
        if cell.is_singleton:
            values.append(str(cell.fixed))
        else:
            values.append(f"({cell.entropy})")
    print(f"Final: [{', '.join(values)}]")
    print()
    
    print("=" * 60)
    print("THE FIELD RELAXES TOWARD THE ANSWER.")
    print("Structure is meaning.")
    print("=" * 60)


def demo_cascade():
    """Demonstrate cascading constraint propagation - the money shot."""
    print("=" * 60)
    print("CASCADING CONSTRAINTS")
    print("When one cell resolves, others follow...")
    print("=" * 60)
    print()
    
    # Create system
    os = HSquaresOS(num_workers=8)
    os.boot()
    print(f"System booted: 8 workers online")
    print()
    
    # Create constraint field
    field = ConstraintField(os)
    
    # This is the money shot: 7 givens force the 8th
    print("=" * 60)
    print("PUZZLE: What must cell 8 be?")
    print("=" * 60)
    print()
    print("8 cells, all must be different, values 1-8 only.")
    print()
    print("Given: cells 1-7 are {1,2,3,4,5,6,7}")
    print("Question: What is cell 8?")
    print()
    
    # Manually restrict domains to 1-8 (not 1-9)
    for nid in range(1, 9):
        field._set_domain(nid, {1, 2, 3, 4, 5, 6, 7, 8})
        field.cells[nid].domain = {1, 2, 3, 4, 5, 6, 7, 8}
    
    # Now set the givens
    for nid in range(1, 8):
        field._set_domain(nid, {nid})
        field.cells[nid].fixed = nid
        field.events.append(PropagationEvent(
            tick=0,
            cell=(field.cells[nid].row, field.cells[nid].col),
            event_type='singleton',
            values={nid},
            reason='given',
            domain_before={1,2,3,4,5,6,7,8},
            domain_after={nid},
        ))
    
    print("Initial state:")
    print(field.show())
    print()
    
    # Propagate
    print("=" * 60)
    print("PROPAGATION")
    print("=" * 60)
    
    for state in field.propagate_stepping(max_steps=10):
        if state['tick'] > 0:
            print(f"\n--- Tick {state['tick']} ---")
            print(field.show())
            
            # Check if cell 8 became singleton
            if field.cells[8].is_singleton:
                print(f"\n  >>> CELL 8 RESOLVED: {field.cells[8].fixed}")
        
        if state['quiescent']:
            if field.cells[8].is_singleton:
                print("\n*** SOLVED! ***")
            break
    
    print()
    print("=" * 60)
    print("WHY is cell 8 = 8?")
    print("=" * 60)
    print()
    print(field.why(8))
    print()
    
    # Summary
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print()
    print(f"Ticks:        {field.ticks}")
    print(f"Eliminations: {field.total_eliminations}")
    print(f"Events:       {len(field.events)}")
    print(f"Messages:     {os.bus.delivered}")
    print()
    
    values = [str(field.cells[nid].fixed) if field.cells[nid].is_singleton else "?" 
              for nid in range(1, 9)]
    print(f"Solution: [{', '.join(values)}]")
    print()
    print("The answer was FORCED by the constraints.")
    print("No search. No guessing. Just propagation.")
    print("=" * 60)


if __name__ == '__main__':
    demo()
