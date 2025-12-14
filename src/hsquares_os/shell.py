"""
SQUARES SHELL (sqsh)

A Bash-like shell for Hollywood Squares OS.

NOT POSIX. NOT Unix. But familiar.

The shell teaches the machine as you use it.

Commands:
    nodes           - List all nodes
    ping <node>     - Ping a node
    send <node> <a> <b> - Send ADD operation
    run <node|all> <op> <a> <b> - Execute operation
    route <op> <a> <b> - Route to best node
    trace [on|off|show] - Tracing control
    stats           - System statistics
    topo            - Show topology
    inspect <node>  - Inspect node state
    reset <node>    - Reset a node
    halt <node>     - Halt a node
    help            - Show help

POSIX-shaped aliases:
    ls    → nodes
    ps    → tasks
    top   → load
"""

import sys
import shlex
from typing import List, Optional, Dict, Any, Callable
from .system import HSquaresOS
from .node_kernel import OpCode, NodeStatus


class SquaresShell:
    """
    The Squares Shell - a Bash-like interface to Hollywood Squares OS.
    
    Familiar surface. Honest architecture.
    """
    
    def __init__(self, os: Optional[HSquaresOS] = None):
        self.os = os or HSquaresOS()
        self.running = False
        self.trace_enabled = False
        self.prompt = '> '
        self.variables: Dict[str, str] = {}
        
        # Command registry
        self.commands: Dict[str, Callable] = {
            'nodes': self.cmd_nodes,
            'ping': self.cmd_ping,
            'send': self.cmd_send,
            'run': self.cmd_run,
            'route': self.cmd_route,
            'trace': self.cmd_trace,
            'stats': self.cmd_stats,
            'topo': self.cmd_topo,
            'inspect': self.cmd_inspect,
            'reset': self.cmd_reset,
            'halt': self.cmd_halt,
            'boot': self.cmd_boot,
            'help': self.cmd_help,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
            
            # POSIX-shaped aliases
            'ls': self.cmd_nodes,
            'ps': self.cmd_tasks,
            'top': self.cmd_load,
            
            # Single-step and replay
            'step': self.cmd_step,
            'pause': self.cmd_pause,
            'resume': self.cmd_resume,
            'record': self.cmd_record,
            'replay': self.cmd_replay,
            'snapshot': self.cmd_snapshot,
            
            # Sorting network
            'sort': self.cmd_sort,
            'sortload': self.cmd_sortload,
            'sortstep': self.cmd_sortstep,
            'sortshow': self.cmd_sortshow,
            
            # Bubble Machine
            'bubble': self.cmd_bubble,
        }
        
        # Sorting network (lazy init)
        self._sorting_net = None
        
        # Bubble machine (lazy init)
        self._bubble = None
        
        # Operation name → code
        self.op_names: Dict[str, int] = {
            'nop': OpCode.NOP,
            'add': OpCode.ADD,
            'sub': OpCode.SUB,
            'cmp': OpCode.CMP,
            'and': OpCode.AND,
            'or': OpCode.OR,
            'xor': OpCode.XOR,
            'shl': OpCode.SHIFT_L,
            'shr': OpCode.SHIFT_R,
        }
    
    def boot(self):
        """Boot the OS."""
        result = self.os.boot()
        online = sum(1 for v in result.values() if v)
        return online
    
    def parse(self, line: str) -> List[str]:
        """Parse a command line into tokens."""
        # Variable substitution
        for name, value in self.variables.items():
            line = line.replace(f'${name}', value)
        
        try:
            return shlex.split(line)
        except ValueError:
            return line.split()
    
    def execute(self, line: str) -> Optional[str]:
        """Execute a command line, return output string."""
        tokens = self.parse(line.strip())
        if not tokens:
            return None
        
        cmd = tokens[0].lower()
        args = tokens[1:]
        
        # Check for variable assignment
        if '=' in cmd and not cmd.startswith('='):
            name, _, value = cmd.partition('=')
            if name:
                self.variables[name] = value
                return None
        
        # Look up command
        handler = self.commands.get(cmd)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                return f"error: {e}"
        else:
            return f"unknown command: {cmd}"
    
    def run_interactive(self):
        """Run interactive shell."""
        self.running = True
        
        print("Hollywood Squares OS - sqsh")
        print("Type 'help' for commands, 'exit' to quit")
        print()
        
        # Auto-boot if not booted
        if not self.os.booted:
            print("Booting...")
            online = self.boot()
            print(f"{online}/{self.os.num_workers} workers online")
            print()
        
        while self.running:
            try:
                line = input(self.prompt)
                output = self.execute(line)
                if output:
                    print(output)
            except EOFError:
                break
            except KeyboardInterrupt:
                print()
                continue
        
        print("Goodbye")
    
    def run_script(self, script: str) -> str:
        """Run a script (multiple lines), return all output."""
        output = []
        for line in script.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            result = self.execute(line)
            if result:
                output.append(result)
        return '\n'.join(output)
    
    # ========== Commands ==========
    
    def cmd_nodes(self, args: List[str]) -> str:
        """List all nodes."""
        lines = []
        for node in self.os.nodes():
            status_icon = {
                'IDLE': '●',
                'BUSY': '◐',
                'ERROR': '✗',
                'OFFLINE': '○',
                'HALTED': '■',
            }.get(node['status'], '?')
            
            role = 'master' if node['id'] == 0 else 'worker'
            lines.append(f"{status_icon} node{node['id']:<2} {role:<8} {node['status']:<8} msgs:{node['msgs']}")
        
        return '\n'.join(lines)
    
    def cmd_ping(self, args: List[str]) -> str:
        """Ping a node."""
        if not args:
            return "usage: ping <node>"
        
        node = self._parse_node(args[0])
        if node is None:
            return f"invalid node: {args[0]}"
        
        result = self.os.ping(node)
        if result:
            status_name = NodeStatus(result[0]).name if result[0] in NodeStatus._value2member_map_ else 'UNKNOWN'
            return f"node{node}: {status_name}, load={result[1]}"
        else:
            return f"node{node}: timeout"
    
    def cmd_send(self, args: List[str]) -> str:
        """Send ADD to a node: send <node> <a> <b>"""
        if len(args) < 3:
            return "usage: send <node> <a> <b>"
        
        node = self._parse_node(args[0])
        if node is None:
            return f"invalid node: {args[0]}"
        
        a = int(args[1])
        b = int(args[2])
        
        result = self.os.exec(node, OpCode.ADD, a, b)
        if result:
            return f"{result[0]}"
        else:
            return "error: no response"
    
    def cmd_run(self, args: List[str]) -> str:
        """Run operation: run <node|all> <op> <a> <b>"""
        if len(args) < 4:
            return "usage: run <node|all> <op> <a> <b>"
        
        target = args[0].lower()
        op_name = args[1].lower()
        a = int(args[2])
        b = int(args[3])
        
        op = self.op_names.get(op_name)
        if op is None:
            return f"unknown op: {op_name}"
        
        if target == 'all':
            results = self.os.broadcast_exec(op, a, b)
            values = [str(r[0]) if r else '?' for r in results.values()]
            return '[' + ', '.join(values) + ']'
        else:
            node = self._parse_node(target)
            if node is None:
                return f"invalid node: {target}"
            
            result = self.os.exec(node, op, a, b)
            if result:
                return f"{result[0]}"
            else:
                return "error: no response"
    
    def cmd_route(self, args: List[str]) -> str:
        """Route work to best node: route <op> <a> <b>"""
        if len(args) < 3:
            return "usage: route <op> <a> <b>"
        
        op_name = args[0].lower()
        a = int(args[1])
        b = int(args[2])
        
        op = self.op_names.get(op_name)
        if op is None:
            return f"unknown op: {op_name}"
        
        result = self.os.route(op, a, b)
        if result:
            return f"→ node{result[0]}: {result[1]}"
        else:
            return "error: no nodes available"
    
    def cmd_trace(self, args: List[str]) -> str:
        """Trace control: trace [on|off|show]"""
        if not args:
            return f"trace: {'on' if self.trace_enabled else 'off'}"
        
        subcmd = args[0].lower()
        if subcmd == 'on':
            self.trace_enabled = True
            return "trace enabled"
        elif subcmd == 'off':
            self.trace_enabled = False
            return "trace disabled"
        elif subcmd == 'show':
            return self.os.fabric.dump_trace()
        else:
            return "usage: trace [on|off|show]"
    
    def cmd_stats(self, args: List[str]) -> str:
        """Show system statistics."""
        stats = self.os.stats()
        lines = []
        for k, v in stats.items():
            lines.append(f"{k}: {v}")
        return '\n'.join(lines)
    
    def cmd_topo(self, args: List[str]) -> str:
        """Show topology."""
        lines = ['root (master)']
        
        online = self.os.fabric.get_online_nodes()
        for i, nid in enumerate(range(1, self.os.num_workers + 1)):
            is_last = (i == self.os.num_workers - 1)
            prefix = '└─' if is_last else '├─'
            status = '●' if nid in online else '○'
            lines.append(f" {prefix} {status} node{nid}")
        
        return '\n'.join(lines)
    
    def cmd_inspect(self, args: List[str]) -> str:
        """Inspect node state."""
        if not args:
            return "usage: inspect <node>"
        
        node = self._parse_node(args[0])
        if node is None:
            return f"invalid node: {args[0]}"
        
        if node == 0:
            kernel = self.os.master
        elif node in self.os.workers:
            kernel = self.os.workers[node]
        else:
            return f"node not found: {node}"
        
        state = kernel.dump_state()
        lines = []
        for k, v in state.items():
            lines.append(f"{k}: {v}")
        return '\n'.join(lines)
    
    def cmd_reset(self, args: List[str]) -> str:
        """Reset a node."""
        if not args:
            return "usage: reset <node>"
        
        node = self._parse_node(args[0])
        if node is None or node == 0:
            return "invalid node (cannot reset master)"
        
        self.os.reset(node)
        return f"node{node} reset"
    
    def cmd_halt(self, args: List[str]) -> str:
        """Halt a node."""
        if not args:
            return "usage: halt <node>"
        
        node = self._parse_node(args[0])
        if node is None or node == 0:
            return "invalid node (cannot halt master)"
        
        self.os.halt(node)
        return f"node{node} halted"
    
    def cmd_boot(self, args: List[str]) -> str:
        """Boot/reboot the system."""
        online = self.boot()
        return f"{online}/{self.os.num_workers} workers online"
    
    def cmd_tasks(self, args: List[str]) -> str:
        """Show running tasks (POSIX alias for ps)."""
        lines = []
        for node in self.os.nodes():
            if node['status'] == 'BUSY':
                lines.append(f"node{node['id']}: busy")
        if not lines:
            return "(no busy nodes)"
        return '\n'.join(lines)
    
    def cmd_load(self, args: List[str]) -> str:
        """Show node loads (POSIX alias for top)."""
        lines = ['NODE  LOAD  STATUS']
        lines.append('-' * 20)
        for i in range(1, self.os.num_workers + 1):
            entry = self.os.fabric.get_node(i)
            if entry:
                bar = '█' * (entry.load // 25) + '░' * (4 - entry.load // 25)
                lines.append(f"{i:<5} {bar}  {entry.status.name}")
        return '\n'.join(lines)
    
    # ========== Single-Step and Replay ==========
    
    def cmd_step(self, args: List[str]) -> str:
        """Single-step execution: step [n]"""
        n = int(args[0]) if args else 1
        
        lines = []
        for i in range(n):
            state = self.os.step()
            
            # Show what happened
            tick = state['tick']
            delivered = state['messages_delivered']
            
            # Find active nodes
            active = [
                f"n{nid}" for nid, s in state['nodes'].items()
                if s['inbox'] > 0 or s['outbox'] > 0
            ]
            
            lines.append(
                f"[{tick:4d}] {delivered} msgs | active: {', '.join(active) or '(none)'}"
            )
        
        return '\n'.join(lines)
    
    def cmd_pause(self, args: List[str]) -> str:
        """Pause execution."""
        self.os.pause()
        return "paused"
    
    def cmd_resume(self, args: List[str]) -> str:
        """Resume execution."""
        self.os.resume()
        return "resumed"
    
    def cmd_record(self, args: List[str]) -> str:
        """Recording control: record [start|stop|show]"""
        if not args:
            return f"recording: {'on' if self.os._recording else 'off'}"
        
        subcmd = args[0].lower()
        if subcmd == 'start':
            self.os.start_recording()
            return "recording started"
        elif subcmd == 'stop':
            log = self.os.stop_recording()
            return f"recording stopped ({len(log)} messages)"
        elif subcmd == 'show':
            rec = self.os.get_recording()
            if not rec:
                return "(empty)"
            lines = []
            for entry in rec[-20:]:  # Last 20
                lines.append(
                    f"[{entry['tick']:3d}] {entry['type']:<12} "
                    f"{entry['src']}→{entry['dst']} {entry['payload']}"
                )
            return '\n'.join(lines)
        else:
            return "usage: record [start|stop|show]"
    
    def cmd_replay(self, args: List[str]) -> str:
        """Replay recorded messages."""
        log = self.os._message_log
        if not log:
            return "no recording to replay"
        
        self.os.replay(log)
        return f"replayed {len(log)} messages"
    
    def cmd_snapshot(self, args: List[str]) -> str:
        """Take system snapshot."""
        snap = self.os.snapshot()
        lines = [f"tick: {snap['tick']}"]
        lines.append(f"master: {snap['master']['status']}")
        for nid, ws in snap['workers'].items():
            lines.append(f"  node{nid}: {ws['status']} recv={ws['msgs_recv']} sent={ws['msgs_sent']}")
        return '\n'.join(lines)
    
    # ========== Sorting Network ==========
    
    def _get_sorting_net(self):
        """Lazy init sorting network."""
        if self._sorting_net is None:
            from .sorting_network import SortingNetwork
            self._sorting_net = SortingNetwork(self.os)
        return self._sorting_net
    
    def cmd_sortload(self, args: List[str]) -> str:
        """Load values into sorting network: sortload <v1> <v2> ..."""
        if not args:
            return "usage: sortload <v1> <v2> ... (up to 8 values)"
        
        values = [int(x) for x in args[:self.os.num_workers]]
        net = self._get_sorting_net()
        net.load(values)
        return net.show()
    
    def cmd_sortstep(self, args: List[str]) -> str:
        """Execute one sorting step: sortstep"""
        net = self._get_sorting_net()
        swaps = net.bubble_step()
        return net.show()
    
    def cmd_sort(self, args: List[str]) -> str:
        """Sort the network: sort [topo]"""
        net = self._get_sorting_net()
        
        # Optional topology change
        if args and args[0] in ('line', 'ring', 'grid'):
            net.set_topology(args[0])
        
        rounds = net.sort()
        return f"Sorted in {rounds} rounds\n\n{net.show()}"
    
    def cmd_sortshow(self, args: List[str]) -> str:
        """Show sorting network state: sortshow [topo]"""
        net = self._get_sorting_net()
        
        if args and args[0] == 'topo':
            return net.show_topology()
        return net.show()
    
    # ========== Bubble Machine ==========
    
    def _get_bubble(self):
        """Lazy init bubble machine."""
        if self._bubble is None:
            from .bubble_machine import BubbleMachine
            self._bubble = BubbleMachine(self.os)
        return self._bubble
    
    def cmd_bubble(self, args: List[str]) -> str:
        """
        Bubble Machine commands.
        
        bubble load <v1> <v2> ...   Load values
        bubble random [seed]        Load random values
        bubble run                  Run until settled
        bubble step                 One cycle
        bubble phase                One phase only
        bubble show                 Show field
        bubble trace [n]            Show last n events
        bubble phases               Show phase schedule
        bubble topo <line|ring|grid> Set topology
        """
        if not args:
            return self.cmd_bubble(['help'])
        
        subcmd = args[0].lower()
        subargs = args[1:]
        
        bubble = self._get_bubble()
        
        if subcmd == 'load':
            if not subargs:
                return "usage: bubble load <v1> <v2> ..."
            values = [int(x) for x in subargs[:self.os.num_workers]]
            bubble.load(values)
            return bubble.show()
        
        elif subcmd == 'random':
            seed = int(subargs[0]) if subargs else None
            bubble.load_random(seed)
            return bubble.show()
        
        elif subcmd == 'run':
            cycles = bubble.run()
            return f"Settled in {cycles} cycles\n\n{bubble.show()}"
        
        elif subcmd == 'step':
            swaps = bubble.step()
            return f"Cycle {bubble.cycles}: {swaps} swaps\n\n{bubble.show()}"
        
        elif subcmd == 'phase':
            name, swaps = bubble.step_phase()
            return f"Phase {name}: {swaps} swaps\n\n{bubble.show()}"
        
        elif subcmd == 'show':
            return bubble.show()
        
        elif subcmd == 'trace':
            n = int(subargs[0]) if subargs else 20
            return bubble.show_trace(n)
        
        elif subcmd == 'phases':
            return bubble.show_phases()
        
        elif subcmd == 'topo':
            if not subargs:
                return f"Current topology: {bubble.topology}"
            topo = subargs[0].lower()
            bubble.set_topology(topo)
            return f"Topology set to: {topo}\n\n{bubble.show_phases()}"
        
        elif subcmd == 'help':
            return """Bubble Machine - A computational field

bubble load <v1> <v2> ...   Load values into field
bubble random [seed]        Load random values
bubble run                  Run until settled
bubble step                 Execute one cycle
bubble phase                Execute one phase
bubble show                 Show current field
bubble trace [n]            Show last n events
bubble phases               Show phase schedule
bubble topo <line|ring|grid> Set topology

"The field relaxes. Structure is meaning." """
        
        else:
            return f"Unknown bubble command: {subcmd}"
    
    def cmd_help(self, args: List[str]) -> str:
        """Show help."""
        return """Hollywood Squares OS - sqsh

Commands:
  nodes           List all nodes
  ping <n>        Ping node n
  send <n> <a> <b>  Add a+b on node n
  run <n|all> <op> <a> <b>  Run operation
  route <op> <a> <b>  Route to best node
  trace [on|off|show]  Trace control
  stats           System statistics
  topo            Show topology
  inspect <n>     Inspect node state
  reset <n>       Reset node
  halt <n>        Halt node
  boot            Boot/reboot system

Single-Step (the magic):
  step [n]        Execute n ticks, show state
  pause           Pause execution
  resume          Resume execution
  record [start|stop|show]  Message recording
  replay          Replay recorded messages
  snapshot        Take system snapshot

Sorting Network (the demo):
  sortload <v1> <v2> ...  Load values
  sortstep        One bubble step
  sort [topo]     Sort to completion
  sortshow [topo] Show state/topology

Operations: nop, add, sub, cmp, and, or, xor, shl, shr
Topologies: line, ring, grid

POSIX aliases: ls→nodes, ps→tasks, top→load"""
    
    def cmd_exit(self, args: List[str]) -> str:
        """Exit the shell."""
        self.running = False
        return ""
    
    # ========== Helpers ==========
    
    def _parse_node(self, s: str) -> Optional[int]:
        """Parse node identifier (e.g., '1', 'node1', 'n1')."""
        s = s.lower().strip()
        if s.startswith('node'):
            s = s[4:]
        elif s.startswith('n'):
            s = s[1:]
        
        try:
            return int(s)
        except ValueError:
            return None


def main():
    """Run the shell."""
    shell = SquaresShell()
    shell.run_interactive()


if __name__ == '__main__':
    main()
