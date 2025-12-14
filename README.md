# Hollywood Squares OS

**A Coordination Operating System for Verified Compositional Intelligence**

[![Paper](https://img.shields.io/badge/Paper-arXiv-red)](paper/main.tex)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## Abstract

Hollywood Squares OS is a distributed microkernel designed for addressable processor networks where message passing serves as the fundamental syscall interface. Unlike traditional operating systems that manage computational resources, Hollywood Squares OS manages *meaning*—coordinating causality, message order, and semantic execution across a field of verified processors.

**Key Result:** Deterministic message passing + bounded local semantics + enforced observability ⇒ global convergence with inherited correctness.

---

## Quick Start

### Installation

```bash
cd arxiv
pip install -r requirements.txt
```

### Run the Demos

```bash
# Bubble Machine - distributed sorting
python experiments/run_bubble_machine.py

# Constraint Field - watch a problem think
python -c "from src.hsquares_os.constraint_field import demo_cascade; demo_cascade()"
```

### Interactive Shell

```python
from src.hsquares_os import HSquaresOS, SquaresShell

os = HSquaresOS(num_workers=8)
os.boot()

shell = SquaresShell(os)
shell.run_interactive()
```

```
> bubble load 64 25 12 22 11 90 42 7
> bubble run
> bubble trace 5
```

---

## Repository Structure

```
arxiv/
├── paper/
│   ├── main.tex          # Paper source
│   ├── references.bib    # Bibliography
│   └── figures/          # Figures
├── src/
│   └── hsquares_os/      # Source code (~4,300 lines)
│       ├── __init__.py
│       ├── message.py           # 16-byte message frames
│       ├── node_kernel.py       # Node kernel
│       ├── fabric_kernel.py     # Fabric services
│       ├── system.py            # Complete system
│       ├── shell.py             # Interactive shell
│       ├── bubble_machine.py    # Demo 1: Distributed sorting
│       └── constraint_field.py  # Demo 2: CSP solver
├── experiments/
│   ├── run_bubble_machine.py # Reproduce paper results
│   └── results/              # Experiment outputs
├── docs/
│   ├── SPEC_SHEET.md         # System specification
│   └── FINDINGS.md           # Research findings
├── README.md                 # This file
├── requirements.txt          # Dependencies
└── LICENSE                   # MIT License
```

---

## The Thesis

> **Structure is meaning.**

The wiring determines the behavior. The messages carry the computation. The trace tells the story.

---

## Key Concepts

### Coordination OS (not Resource OS)

Hollywood Squares does NOT manage:
- CPU time
- Memory pressure
- I/O bandwidth

Hollywood Squares DOES manage:
- **Causality** — ordering of events
- **Message order** — deterministic delivery
- **Semantic execution** — meaningful computation

### The Bubble Machine

A computational field that relaxes toward order through local compare-swap operations.

```
Input:  [64, 25, 12, 22, 11, 90, 42, 7]
Output: [7, 11, 12, 22, 25, 42, 64, 90]

Cycles:   5
Swaps:    18
Messages: 310
```

Every comparison is a message. Every swap is traceable. Every execution is replayable.

### The Constraint Field

A distributed CSP engine that relaxes toward solutions. **You can watch a problem think.**

```
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

Every elimination has a reason. Every reason is traceable. Every solution is explainable.

### Topology is the Algorithm

Same handlers + different wiring = different behavior.

```
Line:  EVEN: (1,2) (3,4) (5,6) (7,8)
       ODD:  (2,3) (4,5) (6,7)

Grid:  H-EVEN, H-ODD, V-EVEN, V-ODD
```

---

## API Reference

### HSquaresOS

```python
os = HSquaresOS(num_workers=8)
os.boot()

# Execute operation
result = os.exec(node=1, op=OpCode.ADD, a=50, b=10)

# Single-step
state = os.step()

# Replay
os.start_recording()
# ... operations ...
log = os.stop_recording()
os.replay(log)
```

### BubbleMachine

```python
bubble = BubbleMachine(os)
bubble.load([64, 25, 12, 22, 11, 90, 42, 7])
bubble.run()

print(bubble.read())        # Final values
print(bubble.show_trace())  # Event log
```

### ConstraintField

```python
from src.hsquares_os import ConstraintField

field = ConstraintField(os)
field.load_puzzle({1: 3, 3: 5, 5: 8, 7: 2})  # Set givens
field.propagate()                             # Run until fixed point

print(field.show())         # Current state
print(field.why(2))         # Explain cell 2's domain
print(field.show_trace())   # All elimination events
```

### Shell Commands

| Command | Description |
|---------|-------------|
| `nodes` | List all nodes |
| `step [n]` | Execute n ticks |
| `bubble load <values>` | Load values into field |
| `bubble run` | Run until settled |
| `bubble step` | One cycle |
| `bubble trace [n]` | Show last n events |
| `bubble phases` | Show phase schedule |

---

## Reproducing Paper Results

### Table 1: Bubble Machine Results

```bash
python experiments/run_bubble_machine.py --output results/table1.json
```

Expected output:
```
Cycles to convergence: 5
Total swaps: 18
Total events: 35
Total ticks: 451
Messages delivered: 310
```

### Trace Verification

```bash
python -c "
from src.hsquares_os import HSquaresOS, BubbleMachine

os = HSquaresOS(num_workers=8)
os.boot()
bubble = BubbleMachine(os)
bubble.load([64, 25, 12, 22, 11, 90, 42, 7])
bubble.run()
print(bubble.show_trace(10))
"
```

---

## Citation

```bibtex
@article{hollywoodsquares2025,
  title={Hollywood Squares OS: A Coordination Operating System 
         for Verified Compositional Intelligence},
  author={Anonymous},
  journal={arXiv preprint},
  year={2025}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## The Core Insight

> **Deterministic message passing + bounded local semantics + enforced observability ⇒ global convergence with inherited correctness.**

This is not about sorting. This is about how correctness scales.

---

*The field relaxes. Structure is meaning.*
