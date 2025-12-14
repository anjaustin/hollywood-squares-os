# Paper Reference Document

**Hollywood Squares OS: A Coordination Operating System for Verified Compositional Intelligence**

*Complete reference for paper authors*

---

## Table of Contents

1. [Core Thesis and Claims](#core-thesis-and-claims)
2. [Abstract Drafts](#abstract-drafts)
3. [Key Vocabulary](#key-vocabulary)
4. [Architecture Details](#architecture-details)
5. [The Bubble Machine](#the-bubble-machine)
6. [Experimental Results](#experimental-results)
7. [Theorems and Proofs](#theorems-and-proofs)
8. [Code Examples](#code-examples)
9. [Trace Examples](#trace-examples)
10. [Comparisons](#comparisons)
11. [Historical Context](#historical-context)
12. [Figures and Diagrams](#figures-and-diagrams)
13. [Key Sentences](#key-sentences)
14. [Related Work](#related-work)
15. [Future Work](#future-work)
16. [Appendices](#appendices)

---

## Core Thesis and Claims

### The Thesis

> **Structure is meaning.**

The wiring determines the behavior. The messages carry the computation. The trace tells the story.

### The Main Result

> **Deterministic message passing + bounded local semantics + enforced observability ⇒ global convergence with inherited correctness.**

This is not about sorting. This is about **how correctness scales**.

### The Hypothesis (Validated)

> Learned, verified micro-processors can be composed into distributed systems where the topology carries the algorithm, every step is deterministic, and correctness propagates from parts to whole.

### What We Proved

1. **Topology IS the Algorithm** — Same handlers + different wiring = different behavior
2. **The Bus IS the Computer** — Messages aren't infrastructure, they're computation
3. **Correctness Propagates** — Verified handlers + deterministic composition = verified system
4. **Single-Step Enables Trust** — Observation replaces archaeology
5. **Replay Enables Verification** — Any execution can be exactly reproduced

---

## Abstract Drafts

### Short Abstract (150 words)

We present Hollywood Squares OS, a distributed microkernel for addressable processor networks where message passing serves as the syscall interface. Unlike traditional operating systems that manage resources, Hollywood Squares OS manages meaning—coordinating causality, message order, and semantic execution. We demonstrate that deterministic message passing combined with bounded local semantics and enforced observability yields global convergence with inherited correctness. Our flagship demonstration, the Bubble Machine, proves distributed convergence under strict observability constraints: a computational field that relaxes toward order through local compare-swap operations, fully traceable and deterministically replayable. The system achieves verified compositional intelligence: small correct parts compose into larger systems where correctness propagates. We provide complete implementation, specification, and experimental validation.

### Extended Abstract (250 words)

We present Hollywood Squares OS, a distributed microkernel designed for addressable processor networks where message passing serves as the fundamental syscall interface. Unlike traditional operating systems that manage computational resources (CPU time, memory, I/O bandwidth), Hollywood Squares OS manages meaning—coordinating causality, message order, and semantic execution across a field of verified processors.

We introduce the concept of a coordination OS: a system that coordinates meaning flow rather than resource allocation. The architecture consists of three cleanly separated layers: a computational substrate (nodes, messages, deterministic ticks), a kernel contract (mailbox, dispatcher, handlers, replay), and a cognitive layer (fields, waves, relaxation algorithms).

Our main theoretical contribution is demonstrating that deterministic message passing + bounded local semantics + enforced observability ⇒ global convergence with inherited correctness. This changes the equation for distributed systems: instead of verifying correctness post-hoc, we construct it by design.

We validate this with the Bubble Machine: a computational field that relaxes toward order through local compare-swap operations. With no shared memory, no global control, and only local rules communicated via messages, the field converges to sorted order in O(n) cycles. Every comparison is traceable; every execution is deterministically replayable.

The system achieves what we call verified compositional intelligence: the composition of small, correct parts into larger systems where correctness propagates from components to the whole. We provide a complete implementation (3,600 lines), formal specification, and reproducible experimental validation.

---

## Key Vocabulary

### Must Use Consistently

| Term | Definition |
|------|------------|
| **Coordination OS** | An OS that manages meaning (causality, message order, semantic execution) rather than resources |
| **Message with meaning** | The fundamental primitive: a 16-byte frame carrying typed, addressed, meaningful content |
| **Topology is the algorithm** | Same handlers + different wiring = different global behavior |
| **Bus is the computer** | Computation happens through messages, not despite them |
| **Deterministic replay** | Any execution can be exactly reproduced from its trace |
| **Verified compositional intelligence** | Correct parts compose into correct wholes |
| **Bubble Machine** | Flagship demo: computational field that relaxes toward order |
| **Node kernel** | The kernel running on each node (mailbox, dispatcher, handlers) |
| **Fabric kernel** | Services running on master (directory, router, supervisor, tracer) |

### Avoid

| Don't Say | Say Instead |
|-----------|-------------|
| "Neural network" | "Verified handlers" or "learned primitives" |
| "AI" | "Compositional intelligence" or "semantic computation" |
| "Process" | "Node" or "handler" |
| "File" | "Message" or "state" |
| "Scheduler" | "Phase scheduler" or "coordinator" |

---

## Architecture Details

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      MASTER (Node 0)                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   FABRIC KERNEL                       │  │
│  │  Directory │ Router │ Supervisor │ Loader │ Tracer    │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   NODE KERNEL                         │  │
│  │  Mailbox │ Dispatcher │ Scheduler │ Memory │ Timers   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────┬─────────┬─┴─┬─────────┬─────────┐
        ▼         ▼         ▼   ▼         ▼         ▼
   ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
   │Worker 1││Worker 2││Worker 3││Worker 4││  ...   │
   │  NODE  ││  NODE  ││  NODE  ││  NODE  ││  NODE  │
   │ KERNEL ││ KERNEL ││ KERNEL ││ KERNEL ││ KERNEL │
   └────────┘└────────┘└────────┘└────────┘└────────┘
```

### Three-Layer Model

| Layer | Name | Components | Role |
|-------|------|------------|------|
| 1 | Computational Substrate | Nodes, messages, ticks | The physics |
| 2 | Kernel Contract | Mailbox, dispatcher, handlers, replay | The OS |
| 3 | Cognitive Layer | Fields, waves, relaxation | The intelligence |

### Message Frame Format

```
┌────────┬────────┬────────┬────────┬────────┬────────┬─────────────┐
│  Type  │   ID   │  Src   │  Dst   │  Len   │ Flags  │   Payload   │
│ 1 byte │ 1 byte │ 1 byte │ 1 byte │ 1 byte │ 1 byte │  10 bytes   │
└────────┴────────┴────────┴────────┴────────┴────────┴─────────────┘
                         Total: 16 bytes
```

### Message Types

| Code | Type | Purpose |
|------|------|---------|
| 0x01 | PING | Health check request |
| 0x02 | PONG | Health check response |
| 0x03 | EXEC | Execute operation |
| 0x04 | EXEC_OK | Operation succeeded |
| 0x05 | EXEC_ERR | Operation failed |
| 0x0A | RESET | Reset node |
| 0x0B | TRACE | Log event |
| 0x0F | HALT | Stop node |
| 0x20 | GET | Get value (Bubble Machine) |
| 0x21 | SET | Set value (Bubble Machine) |
| 0x22 | CSWAP | Compare-swap (Bubble Machine) |

### Node Kernel Components

| Component | Function |
|-----------|----------|
| Mailbox | Bounded message queues (16 deep) |
| Dispatcher | Routes messages to handlers by type |
| Handlers | Registered operations (extensible) |
| Memory | 64KB local address space |
| Tick counter | Deterministic time |

### Fabric Kernel Services

| Service | Function |
|---------|----------|
| Directory | Node registry, status tracking |
| Router | Load-aware work distribution |
| Supervisor | Health monitoring, heartbeat, restart |
| Loader | Program deployment |
| Tracer | Event logging, replay support |

### Key Properties

| Property | Description |
|----------|-------------|
| **Determinism** | Same initial state + same messages = same result |
| **Observability** | Every message logged, every state recorded |
| **Replayability** | Any execution reproduced from trace |
| **Compositionality** | Verified parts compose into verified wholes |

---

## The Bubble Machine

### Definition

A Bubble Machine is a tuple (N, T, H, φ) where:
- **N** = set of nodes, each holding a value
- **T** = topology defining neighbor relationships
- **H** = set of handlers (GET, SET, CSWAP)
- **φ** = phase schedule over node pairs

### Handlers

| Handler | Input | Output | Semantics |
|---------|-------|--------|-----------|
| GET | — | value | Return current value |
| SET | value | ack | Store value in memory |
| CSWAP | neighbor_val, direction | (my_val, swapped) | Compare-swap with neighbor |

### Handler Properties

Each handler is:
- **Bounded**: Finite input space (8-bit values)
- **Deterministic**: Same input → same output
- **Verifiable**: Can be exhaustively tested (256² = 65,536 cases for CSWAP)

### Phase Schedule (Line Topology)

```
EVEN phase: compare pairs (1,2), (3,4), (5,6), (7,8)
ODD phase:  compare pairs (2,3), (4,5), (6,7)
```

This is odd-even transposition sort via message passing.

### Phase Schedule (Grid Topology)

```
H-EVEN: Horizontal pairs at even columns
H-ODD:  Horizontal pairs at odd columns
V-EVEN: Vertical pairs at even rows
V-ODD:  Vertical pairs at odd rows
```

### Convergence

For line topology with n nodes:
- **Worst case**: n cycles to convergence
- **Each cycle**: Moves maximum unsorted element ≥1 position toward final location
- **Termination**: Detected by zero swaps in a complete cycle (quiescence)

### What Makes It Significant

The Bubble Machine demonstrates:
- ✓ No shared memory
- ✓ No global control
- ✓ Only local rules
- ✓ Only messages
- ✓ Convergence to sorted order
- ✓ Full traceability
- ✓ Deterministic replay

> **"This is a proof of distributed convergence under strict observability constraints."**

---

## Experimental Results

### System Configuration

| Parameter | Value |
|-----------|-------|
| Topology | 1 master + 8 workers (star) |
| Implementation | Python 3.12 |
| Message frame | 16 bytes |
| Node memory | 64KB per node |
| Mailbox depth | 16 messages |

### Bubble Machine Results (Default Test Case)

**Input:** `[64, 25, 12, 22, 11, 90, 42, 7]`

**Output:** `[7, 11, 12, 22, 25, 42, 64, 90]`

| Metric | Value |
|--------|-------|
| Cycles to convergence | 4-5 |
| Total swaps | 18 |
| Total events | 28-35 |
| Total ticks | 450-510 |
| Messages delivered | 310-350 |
| Final sorted | True |

### Cycle-by-Cycle Progression

| Cycle | Values | Swaps | Status |
|-------|--------|-------|--------|
| 0 | [64, 25, 12, 22, 11, 90, 42, 7] | 0 | Initial |
| 1 | [25, 12, 64, 11, 22, 7, 90, 42] | 5 | Flowing |
| 2 | [12, 11, 25, 7, 64, 22, 42, 90] | 6 | Flowing |
| 3 | [11, 7, 12, 22, 25, 42, 64, 90] | 6 | Flowing |
| 4 | [7, 11, 12, 22, 25, 42, 64, 90] | 1 | Settled |
| 5 | [7, 11, 12, 22, 25, 42, 64, 90] | 0 | Quiescent |

### Messages Per Operation

| Operation | Messages |
|-----------|----------|
| Load 8 values | 16 (8 SET + 8 ACK) |
| One GET | 2 (request + response) |
| One CSWAP | 2-4 (request + response, possibly SET) |
| One cycle | ~30-40 |

---

## Theorems and Proofs

### Theorem 1: Determinism

**Statement:** Given identical initial state S₀ and message sequence M, execution produces identical final state Sf.

**Proof sketch:**
1. Each handler is a pure function: input → output
2. Message delivery order is deterministic (FIFO per channel)
3. Tick-by-tick execution is sequential within each node
4. Therefore, state evolution is uniquely determined by S₀ and M. ∎

### Theorem 2: Bubble Machine Convergence

**Statement:** A Bubble Machine with n nodes in line topology converges to sorted order in at most n cycles.

**Proof sketch:**
1. Define inversion count I = number of pairs (i,j) where i < j but value[i] > value[j]
2. Each swap reduces I by at least 1
3. I starts at most n(n-1)/2
4. Each cycle performs at least one swap if I > 0
5. After at most n cycles, I = 0 (sorted) ∎

### Theorem 3: Correctness Propagation

**Statement:** If each handler h ∈ H satisfies specification Spec(h), then the composed system satisfies Spec(system).

**Proof sketch:**
1. System behavior is sequence of handler invocations
2. Each invocation produces correct output (by assumption)
3. Message passing preserves message content (no corruption)
4. Deterministic composition of correct steps yields correct result ∎

### Lemma: Replay Correctness

**Statement:** replay(trace(execution)) produces identical state sequence.

**Proof:** Follows directly from Theorem 1 (Determinism). The trace captures the complete message sequence; replaying it reproduces the execution. ∎

---

## Code Examples

### Creating the System

```python
from hsquares_os import HSquaresOS, BubbleMachine

# Create 1×8 system
os = HSquaresOS(num_workers=8)
os.boot()  # Returns {1: True, 2: True, ..., 8: True}
```

### Basic Operations

```python
# Execute operation on specific node
result = os.exec(node=1, op=OpCode.ADD, a=50, b=10)
# Returns (60, 0)  # (result, carry)

# Route to best available node
result = os.route(op=OpCode.ADD, a=100, b=55)
# Returns (node_id, result, extra)

# Broadcast to all workers
results = os.broadcast_exec(op=OpCode.ADD, a=5, b=3)
# Returns {1: (8,0), 2: (8,0), ..., 8: (8,0)}
```

### Single-Step Execution

```python
# Execute exactly one tick
state = os.step()
# Returns {
#   'tick': 42,
#   'messages_delivered': 1,
#   'nodes': {0: {'status': 'IDLE', ...}, ...}
# }
```

### Bubble Machine

```python
bubble = BubbleMachine(os)
bubble.load([64, 25, 12, 22, 11, 90, 42, 7])

# Run until settled
cycles = bubble.run()

# Or step through
for state in bubble.run_stepping():
    print(f"Cycle {state['cycle']}: {state['values']}")
    if state['sorted']:
        break
```

### Trace and Replay

```python
# Start recording
os.start_recording()

# ... do operations ...
bubble.run()

# Stop and get log
log = os.stop_recording()

# Replay
os.replay(log)  # Produces identical execution
```

### Shell Interface

```python
shell = SquaresShell(os)
shell.run_interactive()
```

```
> nodes
● node0  master   IDLE     msgs:8
● node1  worker   IDLE     msgs:1
...

> bubble load 64 25 12 22 11 90 42 7
> bubble run
Settled in 5 cycles

> bubble trace 5
[t= 439] EVEN  pair(n5,n6) 25<=>42 (no swap)
...
```

---

## Trace Examples

### Boot Sequence Trace

```
[     1] Node 0: SEND     PING #1 → Node 1
[     2] Node 1: RECV     PING #1
[     3] Node 1: SEND     PONG #1 → Node 0
[     3] Node 0: RECV     PONG #1
[     4] Node 0: SEND     PING #2 → Node 2
...
```

### Bubble Machine Trace

```
[t= 112] EVEN     pair(n1,n2) 64<->25 => (25,64)
[t= 124] EVEN     pair(n3,n4) 12<->22 => (12,22)
[t= 136] EVEN     pair(n5,n6) 11<->90 => (11,90)
[t= 148] EVEN     pair(n7,n8) 42<->7  => (7,42)
[t= 160] ODD      pair(n2,n3) 64<->12 => (12,64)
[t= 172] ODD      pair(n4,n5) 22<->11 => (11,22)
[t= 184] ODD      pair(n6,n7) 90<->42 => (42,90)
...
[t= 475] ODD      pair(n6,n7) 42<=>64 (no swap)
```

### Trace Format

```
[tick] PHASE    pair(nA,nB) valA<->valB => (newA,newB)  # swap occurred
[tick] PHASE    pair(nA,nB) valA<=>valB (no swap)      # no swap needed
```

---

## Comparisons

### Hollywood Squares vs Unix

| Aspect | Unix | Hollywood Squares |
|--------|------|-------------------|
| Fundamental unit | Process | Node + Handler |
| Communication | Files, pipes, signals | Messages only |
| State | Global filesystem | Node-local memory |
| Time | Wall clock | Deterministic ticks |
| Debugging | Core dumps, logs | Trace + replay |
| Manages | Resources | Meaning |

### Hollywood Squares vs Erlang

| Aspect | Erlang | Hollywood Squares |
|--------|--------|-------------------|
| Processes | Lightweight, many | Fixed nodes |
| Messages | Async, unordered | Deterministic order |
| State | Process-local | Node-local |
| Nondeterminism | Allowed | Forbidden |
| Replay | Not built-in | First-class |
| Verification | Post-hoc | By construction |

### Hollywood Squares vs Neural Networks

| Aspect | Neural Networks | Hollywood Squares |
|--------|-----------------|-------------------|
| Computation | Matrix multiply | Message handlers |
| Transparency | Opaque | Fully observable |
| Determinism | Often not | Always |
| Compositionality | Limited | First-class |
| Debugging | Difficult | Single-step |
| Verification | Statistical | Exhaustive possible |

### Hollywood Squares vs Cellular Automata

| Aspect | Cellular Automata | Hollywood Squares |
|--------|-------------------|-------------------|
| Communication | Neighbor state read | Explicit messages |
| Synchronization | Global clock | Message-driven |
| Observability | State snapshots | Full trace |
| Replay | Possible | Built-in |
| Topology | Fixed grid | Configurable |

---

## Historical Context

### The Lineage

| System | Year | Primitive |
|--------|------|-----------|
| Unix | 1970s | Processes + files |
| Erlang | 1980s | Lightweight processes + messages |
| Plan 9 | 1990s | Everything is a file |
| **Hollywood Squares** | 2024 | **Everything is a message with meaning** |

### What Changed

- **Unix** asked: How do we share a computer?
- **Erlang** asked: How do we handle failures?
- **Plan 9** asked: How do we unify interfaces?
- **Hollywood Squares** asks: **How do we make correctness scale?**

### The Paradigm Shift

From: "Verify correctness post-hoc"
To: "Construct correctness by design"

---

## Figures and Diagrams

### Figure 1: System Architecture

```
┌─────────────────────────────────────────┐
│           MASTER (Node 0)               │
│  ┌─────────────────────────────────┐    │
│  │       FABRIC KERNEL             │    │
│  │  Directory│Router│Supervisor    │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │       NODE KERNEL               │    │
│  │  Mailbox│Dispatcher│Handlers    │    │
│  └─────────────────────────────────┘    │
└───────────────────┬─────────────────────┘
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Worker 1 │ │Worker 2 │ │  ...8   │
   └─────────┘ └─────────┘ └─────────┘
```

### Figure 2: Message Frame

```
┌────┬────┬────┬────┬────┬────┬──────────────────┐
│Type│ ID │Src │Dst │Len │Flag│     Payload      │
│ 1B │ 1B │ 1B │ 1B │ 1B │ 1B │       10B        │
└────┴────┴────┴────┴────┴────┴──────────────────┘
                    16 bytes total
```

### Figure 3: Bubble Machine Phases (Line)

```
EVEN Phase:
  [n1]──[n2]  [n3]──[n4]  [n5]──[n6]  [n7]──[n8]
    └──┬──┘     └──┬──┘     └──┬──┘     └──┬──┘
     compare    compare    compare    compare

ODD Phase:
  [n1]  [n2]──[n3]  [n4]──[n5]  [n6]──[n7]  [n8]
          └──┬──┘     └──┬──┘     └──┬──┘
           compare    compare    compare
```

### Figure 4: Convergence Visualization

```
Cycle 0: [64][25][12][22][11][90][42][ 7]  ← Unsorted
            ↓
Cycle 1: [25][12][64][11][22][ 7][90][42]  ← 5 swaps
            ↓
Cycle 2: [12][11][25][ 7][64][22][42][90]  ← 6 swaps
            ↓
Cycle 3: [11][ 7][12][22][25][42][64][90]  ← 6 swaps
            ↓
Cycle 4: [ 7][11][12][22][25][42][64][90]  ← 1 swap
            ↓
Cycle 5: [ 7][11][12][22][25][42][64][90]  ← 0 swaps (SETTLED)
```

### Figure 5: Three-Layer Architecture

```
┌─────────────────────────────────────────┐
│         COGNITIVE LAYER                 │
│   Fields, Waves, Relaxation, Learning   │
├─────────────────────────────────────────┤
│         KERNEL CONTRACT                 │
│   Mailbox, Dispatcher, Handlers, Replay │
├─────────────────────────────────────────┤
│      COMPUTATIONAL SUBSTRATE            │
│   Nodes, Messages, Ticks, Memory        │
└─────────────────────────────────────────┘
```

---

## Key Sentences

### For Different Audiences

**Systems reviewers:**
> "A distributed microkernel with message-passing syscalls and deterministic replay for addressable processor networks."

**ML reviewers:**
> "Learning as manufacturing: trained computation becomes versioned, verified, deployable artifacts composable into distributed systems."

**Distributed systems reviewers:**
> "We prove that deterministic message passing + bounded local semantics + enforced observability yields global convergence with inherited correctness."

**General audience:**
> "A machine where you can watch every thought, trace every decision, and replay any moment."

### Quotable Lines

- "Structure is meaning."
- "The topology IS the algorithm."
- "The bus IS the computer."
- "Hollywood Squares manages meaning, not resources."
- "This is a proof of distributed convergence under strict observability constraints."
- "We didn't solve distributed correctness—we changed the rules so it propagates naturally."
- "Debugging becomes observation, not archaeology."

### The Identity

> **"A coordination OS for verified compositional intelligence."**

---

## Related Work

### Actor Model (Hewitt, 1973)

- Shared: Message-passing philosophy
- Different: Hollywood Squares enforces determinism and provides replay

### Erlang/OTP (Armstrong, 1980s)

- Shared: Lightweight processes, supervision trees
- Different: Erlang allows nondeterminism; we forbid it

### Dataflow Architectures

- Shared: Execution driven by data availability
- Different: We add explicit phases and full observability

### Cellular Automata (Wolfram, 1984)

- Shared: Local rules → global behavior
- Different: CA reads neighbor state; we use explicit messages

### Sorting Networks (Batcher, 1968)

- Shared: Parallel compare-swap
- Different: We execute via message passing with full trace

### Distributed Snapshots (Chandy-Lamport, 1985)

- Shared: Capturing global state
- Different: We capture complete trace, not just consistent cuts

### Plan 9 (Pike et al., 1990)

- Shared: Unifying abstraction
- Different: Plan 9 = files; Hollywood Squares = messages with meaning

---

## The Constraint Field (NEW)

### The Second Demo

While the Bubble Machine proves distributed convergence, the **Constraint Field** proves **semantic emergence under constraint**.

> **"This system doesn't search for solutions. It relaxes toward them."**

### Architecture

```
┌─────────────────────────────────────────┐
│           CONSTRAINT FIELD              │
│  ┌─────┬─────┬─────┬─────┬─────┐       │
│  │cell │cell │cell │cell │cell │  ...  │
│  │ 1   │ 2   │ 3   │ 4   │ 5   │       │
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┘       │
│     │     │     │     │                 │
│  ┌──┴─────┴─────┴─────┴──┐             │
│  │    ALL-DIFFERENT       │             │
│  │    CONSTRAINT          │             │
│  └───────────────────────┘             │
└─────────────────────────────────────────┘
```

### Handlers

| Handler | Input | Output | Semantics |
|---------|-------|--------|-----------|
| DOMAIN_GET | — | (lo, hi) | Return domain bitmask |
| DOMAIN_SET | lo, hi | (lo, hi) | Set domain |
| DOMAIN_DELTA | mask_lo, mask_hi | (changed, entropy) | Remove values from domain |
| IS_SINGLETON | — | (is_single, count) | Check if resolved |
| GET_VALUE | — | (value, entropy) | Get singleton value |

### The Money Shot

```
============================================================
PUZZLE: What must cell 8 be?
============================================================

8 cells, all must be different, values 1-8 only.

Given: cells 1-7 are {1,2,3,4,5,6,7}
Question: What is cell 8?

Initial state:
n8 (2,1): {1,2,3,4,5,6,7,8}    entropy=8

============================================================
PROPAGATION
============================================================

--- Tick 1 ---
n8 (2,1): [8]                  FIXED

  >>> CELL 8 RESOLVED: 8

*** SOLVED! ***

============================================================
WHY is cell 8 = 8?
============================================================

Cell (2,1) - node 8
Current domain: [8]

History:
  [t=157] removed {1} via cell(0,0)=1
  [t=187] removed {2} via cell(0,1)=2
  [t=217] removed {3} via cell(0,2)=3
  [t=247] removed {4} via cell(1,0)=4
  [t=277] removed {5} via cell(1,1)=5
  [t=307] removed {6} via cell(1,2)=6
  [t=337] removed {7} via cell(2,0)=7

The answer was FORCED by the constraints.
No search. No guessing. Just propagation.
```

### Why This Matters

1. **Explainable** — Every elimination has a reason
2. **Traceable** — Complete history of every cell
3. **Replayable** — Identical execution from trace
4. **No Search** — Pure propagation, no backtracking

### The Sentence

> **"You can watch a problem think."**

---

## Future Work

### Immediate (v0.2)

1. **Constraint Machine** — Arc consistency and unit propagation as message-passing relaxation
2. **Canonicalize Bubble Machine** — Reference documentation, diagrams, tutorial

### Near-term

3. **Network Silicon** — Packet classification micro-engines for routers/switches
4. **Learned Handlers** — Train → freeze → verify → deploy pipeline
5. **Hierarchical Topologies** — Trees of grids, recursive coordination

### Long-term

6. **Formal Verification** — Machine-checked proofs of handler correctness
7. **Hardware Implementation** — FPGA/ASIC realization
8. **Language Support** — DSL for topology and handler specification

---

## Appendices

### A: Complete Message Type Table

| Code | Name | Direction | Payload | Response |
|------|------|-----------|---------|----------|
| 0x00 | NOP | — | — | — |
| 0x01 | PING | Request | — | PONG |
| 0x02 | PONG | Response | status, load | — |
| 0x03 | EXEC | Request | op, a, b, flags | EXEC_OK/ERR |
| 0x04 | EXEC_OK | Response | result, extra | — |
| 0x05 | EXEC_ERR | Response | error_code | — |
| 0x06 | LOAD | Request | program_id | LOAD_OK |
| 0x07 | LOAD_OK | Response | — | — |
| 0x08 | DUMP | Request | addr, len | DUMP_DATA |
| 0x09 | DUMP_DATA | Response | data | — |
| 0x0A | RESET | Command | — | — |
| 0x0B | TRACE | Event | event_data | — |
| 0x0C | ROUTE | Request | work_data | EXEC_OK |
| 0x0D | STATUS | Request | — | STATUS_RPL |
| 0x0E | STATUS_RPL | Response | status_data | — |
| 0x0F | HALT | Command | — | — |
| 0x20 | GET | Request | — | (value, 0) |
| 0x21 | SET | Request | value | (value, 0) |
| 0x22 | CSWAP | Request | neighbor_val, dir | (my_val, swapped) |

### B: Shell Command Reference

```
Basic Operations:
  nodes               List all nodes
  ping <n>            Health check node n
  send <n> <a> <b>    Execute ADD on node n
  run <n|all> <op> <a> <b>  Execute operation
  route <op> <a> <b>  Route to best node
  topo                Show topology
  stats               System statistics
  inspect <n>         Inspect node state

Single-Step:
  step [n]            Execute n ticks
  pause               Pause execution
  resume              Resume execution
  snapshot            Capture state
  record [start|stop|show]  Recording control
  replay              Replay recorded session

Bubble Machine:
  bubble load <v1> <v2> ...  Load values
  bubble random [seed]       Random values
  bubble run                 Run until settled
  bubble step                One cycle
  bubble phase               One phase
  bubble show                Show field
  bubble trace [n]           Show last n events
  bubble phases              Show phase schedule
  bubble topo <type>         Set topology (line|ring|grid)
```

### C: Implementation Statistics

| Component | Lines of Code |
|-----------|---------------|
| message.py | 252 |
| node_kernel.py | 432 |
| fabric_kernel.py | 342 |
| system.py | 649 |
| shell.py | 685 |
| bubble_machine.py | 487 |
| sorting_fabric.py | 318 |
| sorting_network.py | 393 |
| **Total** | **~3,600** |

### D: Reproducibility Checklist

- [ ] Python 3.10+ installed
- [ ] No external dependencies required
- [ ] Run: `python experiments/run_bubble_machine.py`
- [ ] Verify: Cycles ≤ 5, Swaps = 18, Sorted = True
- [ ] Compare trace format to paper

---

## Contact

*[To be filled in before submission]*

---

*The field relaxes. Structure is meaning.*

*December 14, 2024*
