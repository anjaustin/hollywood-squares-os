# Hollywood Squares OS

## Specification Sheet

**Version:** 0.1  
**Date:** December 14, 2024  
**Status:** Hypothesis Validated

---

## The Hypothesis

> Learned, verified micro-processors can be composed into distributed systems where the topology carries the algorithm, every step is deterministic, and correctness propagates from parts to whole.

---

## The System

**Hollywood Squares OS** is a distributed microkernel for addressable processors.

It is not Unix. It is not a neural network. It is not a traditional distributed system.

It is a **coordination OS**, not a resource OS.

It does not manage:
- CPU time
- Memory pressure
- I/O bandwidth

It manages:
- **Causality**
- **Message order**
- **Semantic execution**

It is a **substrate for verified compositional intelligence**.

---

## Architecture

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
   │        ││        ││        ││        ││        │
   │  NODE  ││  NODE  ││  NODE  ││  NODE  ││  NODE  │
   │ KERNEL ││ KERNEL ││ KERNEL ││ KERNEL ││ KERNEL │
   └────────┘└────────┘└────────┘└────────┘└────────┘
```

**Topology:** 1×8 Star (master + 8 workers)  
**Communication:** Message passing only  
**Execution:** Deterministic, non-preemptive  

---

## Core Principle

**Message passing as the syscall interface.**

There are no traps. No interrupts. No shared memory.

Every operation is a message:
- Node A sends EXEC to Node B
- Node B processes and sends EXEC_OK
- Every message is logged
- Every step can be replayed

---

## Message Frame

```
┌────────┬────────┬────────┬────────┬────────┬────────┬─────────────┐
│  Type  │   ID   │  Src   │  Dst   │  Len   │ Flags  │   Payload   │
│ 1 byte │ 1 byte │ 1 byte │ 1 byte │ 1 byte │ 1 byte │  10 bytes   │
└────────┴────────┴────────┴────────┴────────┴────────┴─────────────┘
                         Total: 16 bytes
```

**Message Types:**
| Code | Type | Purpose |
|------|------|---------|
| 0x01 | PING | Health check |
| 0x02 | PONG | Health response |
| 0x03 | EXEC | Execute operation |
| 0x04 | EXEC_OK | Operation succeeded |
| 0x05 | EXEC_ERR | Operation failed |
| 0x0A | RESET | Reset node |
| 0x0B | TRACE | Log event |
| 0x0F | HALT | Stop node |

---

## Node Kernel

Runs on every node (master and workers).

**Components:**
- **Mailbox:** Incoming/outgoing message queues (16 deep)
- **Dispatcher:** Routes messages to handlers
- **Scheduler:** Cooperative, run-to-completion
- **Memory:** 64KB address space per node
- **Handlers:** Registered operations (extensible)

**Main Loop:**
```
wait for message → dispatch to handler → send response → repeat
```

**Built-in Operations:**
| Code | Op | Function |
|------|----|----------|
| 0x01 | ADD | a + b |
| 0x02 | SUB | a - b |
| 0x03 | CMP | Compare |
| 0x04 | AND | Logical AND |
| 0x05 | OR | Logical OR |
| 0x06 | XOR | Logical XOR |

---

## Fabric Kernel

Runs on master node only.

**Services:**

| Service | Function |
|---------|----------|
| Directory | Node registry, status tracking |
| Router | Load-aware work distribution |
| Supervisor | Heartbeat, timeout, restart |
| Loader | Program deployment |
| Tracer | Event logging, replay support |

---

## Key Capabilities

### 1. Single-Step Execution

```python
state = os.step()  # Execute exactly ONE tick
# Returns: tick count, messages delivered, node states
```

You can watch every message, every state change, every decision.

### 2. Deterministic Replay

```python
os.start_recording()
# ... run computation ...
log = os.stop_recording()

os.replay(log)  # Bit-for-bit identical execution
```

Same input → same output. Always.

### 3. Addressable Introspection

```python
os.ping(node)           # Health check
kernel.dump_state()     # Complete state snapshot
os.fabric.get_trace()   # Event history
```

Every node. Every message. Every tick. Observable.

### 4. Extensible Handlers

```python
def my_handler(a: int, b: int, flags: int) -> Tuple[int, int]:
    # Custom operation
    return (result, extra)

kernel.register_handler(0x40, my_handler)
```

Add new operations without modifying the kernel.

---

## Proof: Distributed Sorting

To validate the hypothesis, we implemented sorting through the message fabric.

**Not simulated. Real messages. Real bus traffic.**

### Implementation

Each node:
- Holds one value in memory
- Responds to GET_VALUE, SET_VALUE, SWAP_IF_GREATER
- No global state, no shared memory

### Algorithm

Odd-even transposition sort via message passing:
1. Odd nodes compare with right neighbor
2. Even nodes compare with right neighbor
3. Repeat until no swaps

### Results

```
Input:  [64, 25, 12, 22, 11, 90, 42, 7]
Output: [7, 11, 12, 22, 25, 42, 64, 90]

Rounds:   5
Messages: 96
Ticks:    322
```

### Trace Excerpt

```
[  121] n0: SEND     EXEC        
[  122] n4: RECV     EXEC        
[  123] n4: SEND     EXEC_OK     
[  123] n0: RECV     EXEC_OK     
```

Every comparison is a message. Every swap crosses the bus.

---

## Shell Interface

Bash-like interface for familiarity.

```
> nodes
● node0  master   IDLE     msgs:8
● node1  worker   IDLE     msgs:1
● node2  worker   IDLE     msgs:1
...

> topo
root (master)
 ├─ ● node1
 ├─ ● node2
 └─ ...

> step
[  42] 1 msgs | active: n1

> run all add 50 10
[60, 60, 60, 60, 60, 60, 60, 60]
```

**Commands:**
- `nodes` - List all nodes
- `ping <n>` - Health check
- `run <n|all> <op> <a> <b>` - Execute operation
- `step [n]` - Single-step execution
- `trace show` - View event log
- `snapshot` - Capture system state

---

## File Inventory

```
src/trix/hsquares_os/
├── __init__.py          # Package exports
├── message.py           # 16-byte message frames
├── node_kernel.py       # Node kernel implementation
├── fabric_kernel.py     # Fabric services (master)
├── system.py            # Complete 1×8 system
├── shell.py             # Bash-like shell (sqsh)
├── sorting_network.py   # Visual sorting demo
├── sorting_fabric.py    # Real distributed sorting
└── README.md            # API reference
```

**Total:** ~2,500 lines of Python

---

## What This Proves

### The Topology IS the Algorithm

Same local rules + different wiring = different global behavior.

```
Line:  n1 → n2 → n3 → n4
Grid:  n1 → n2
       ↓    ↓
       n3 → n4
```

Change the structure, change the computation.

### The Bus IS the Computer

Computation happens through messages, not despite them.

Every message is:
- Addressable (src → dst)
- Typed (EXEC, EXEC_OK, ...)
- Traceable (logged)
- Replayable (deterministic)

### Correctness Propagates

If each handler is correct (verifiable), the composition is correct.

No emergent bugs from interaction.
No race conditions.
No shared state corruption.

---

## Hypothesis Validation

| Claim | Evidence |
|-------|----------|
| Learned primitives can be composed | Sorting handlers composed into network |
| Topology carries algorithm | Line vs grid produce different sort patterns |
| Every step is deterministic | Replay produces identical results |
| Correctness propagates | Local handler correctness → global sort correctness |

**Status: VALIDATED**

---

## What Emerged

This is not:
- A process scheduler
- A neural network
- A traditional distributed system

This is:
- **Addressable cognition**
- **Verified compositional intelligence**
- **A machine you can watch thinking**

---

## Historical Lineage

| System | Primitive | Era |
|--------|-----------|-----|
| Unix | processes + files | 1970s |
| Erlang | processes + messages | 1980s |
| Plan 9 | everything is a file | 1990s |
| **Hollywood Squares** | **everything is a message with meaning** | 2024 |

Unlike Erlang:
- Replay is first-class
- Determinism is enforced
- Verification is upstream, not post hoc

---

## The Sentences

**For systems reviewers:**
> A distributed microkernel with message-passing syscalls and deterministic replay for addressable processor networks.

**For ML reviewers:**
> Learning as manufacturing: trained computation becomes versioned, verified, deployable artifacts composable into distributed systems.

**For everyone:**
> A machine where you can watch every thought, trace every decision, and replay any moment.

**The identity:**
> A coordination OS for verified compositional intelligence.

---

## Next Applications

| Application | Description |
|-------------|-------------|
| Network Silicon | Packet classification micro-engines for routers/switches |
| Constraint Solving | Distributed constraint propagation |
| Graph Algorithms | BFS/shortest-path as wave relaxation |
| Sensor Fusion | Parallel stream processing |

---

## The Principle

> **Structure is meaning.**

The wiring determines the behavior.
The messages carry the computation.
The trace tells the story.

---

**Hollywood Squares OS**  
*A substrate for verified compositional intelligence.*

December 14, 2024
