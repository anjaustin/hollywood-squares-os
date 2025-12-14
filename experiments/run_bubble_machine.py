#!/usr/bin/env python3
"""
Bubble Machine Experiment

Reproduces the results from the paper:
- 8-node line topology
- Odd-even transposition sort
- Full trace and metrics

Usage:
    python run_bubble_machine.py [--seed SEED] [--output results/]
"""

import sys
import json
import argparse
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from hsquares_os import HSquaresOS, BubbleMachine


def run_experiment(seed: int = None, verbose: bool = True) -> dict:
    """
    Run the Bubble Machine experiment.
    
    Returns metrics dict.
    """
    # Create system
    os = HSquaresOS(num_workers=8)
    boot_result = os.boot()
    
    if verbose:
        online = sum(1 for v in boot_result.values() if v)
        print(f"System booted: {online}/8 workers online")
    
    # Create Bubble Machine
    bubble = BubbleMachine(os)
    
    # Load data
    if seed is not None:
        bubble.load_random(seed)
    else:
        # Default test case from paper
        bubble.load([64, 25, 12, 22, 11, 90, 42, 7])
    
    initial_values = bubble.read()
    
    if verbose:
        print(f"\nInitial: {initial_values}")
        print(f"Topology: {bubble.topology}")
        print(f"Phases: {[p.name for p in bubble.phases]}")
        print()
    
    # Run with stepping
    cycle_data = []
    
    for state in bubble.run_stepping(max_cycles=100):
        cycle_data.append({
            'cycle': state['cycle'],
            'values': state['values'].copy(),
            'sorted': state['sorted'],
            'swaps': state['swaps'],
        })
        
        if verbose and state['cycle'] > 0:
            status = 'SETTLED' if state['sorted'] else 'flowing'
            print(f"Cycle {state['cycle']}: {state['values']} [{status}]")
        
        if state['sorted']:
            break
    
    final_values = bubble.read()
    
    # Collect metrics
    metrics = {
        'initial_values': initial_values,
        'final_values': final_values,
        'cycles': bubble.cycles,
        'total_swaps': bubble.total_swaps,
        'total_events': len(bubble.events),
        'total_ticks': os.tick_count,
        'messages_delivered': os.bus.delivered,
        'topology': bubble.topology,
        'num_workers': os.num_workers,
        'sorted': bubble._is_sorted(final_values),
        'cycle_data': cycle_data,
    }
    
    if verbose:
        print(f"\n{'='*50}")
        print("RESULTS")
        print(f"{'='*50}")
        print(f"Cycles to convergence: {metrics['cycles']}")
        print(f"Total swaps: {metrics['total_swaps']}")
        print(f"Total events: {metrics['total_events']}")
        print(f"Total ticks: {metrics['total_ticks']}")
        print(f"Messages delivered: {metrics['messages_delivered']}")
        print(f"Final sorted: {metrics['sorted']}")
    
    return metrics


def save_results(metrics: dict, output_path: Path):
    """Save results to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Bubble Machine Experiment')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for initial values')
    parser.add_argument('--output', type=str, default='results/bubble_machine.json',
                        help='Output file for results')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress verbose output')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("BUBBLE MACHINE EXPERIMENT")
    print("Hollywood Squares OS - Paper Reproduction")
    print("=" * 60)
    print()
    
    metrics = run_experiment(seed=args.seed, verbose=not args.quiet)
    
    if args.output:
        save_results(metrics, Path(args.output))
    
    print()
    print("=" * 60)
    print("THE FIELD RELAXES. STRUCTURE IS MEANING.")
    print("=" * 60)


if __name__ == '__main__':
    main()
