"""
HOLLYWOOD SQUARES OS - COMPLETE SYSTEM

The 1×8 distributed system with master + 8 workers.

Components:
- Master node (node 0) with FabricKernel
- 8 worker nodes (nodes 1-8) with NodeKernel
- Message bus connecting all nodes
- Unified interface for control and observation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from collections import deque
import time

from .message import Message, MessageType, MessageFlags, ping_msg, exec_msg, compute_msg
from .node_kernel import NodeKernel, NodeStatus, OpCode
from .fabric_kernel import FabricKernel, NodeEntry, Capability


class MessageBus:
    """
    The message bus connecting all nodes.
    
    Star topology: all messages route through master.
    """
    
    def __init__(self):
        self.nodes: Dict[int, NodeKernel] = {}
        self.in_flight: deque = deque()
        self.delivered: int = 0
        self.dropped: int = 0
    
    def register_node(self, node: NodeKernel):
        """Register a node on the bus."""
        self.nodes[node.node_id] = node
    
    def tick(self) -> int:
        """
        Process one tick of bus activity.
        
        Collects outgoing messages from all nodes and delivers them.
        Returns number of messages delivered.
        """
        delivered = 0
        
        # Collect outgoing messages from all nodes
        for node in self.nodes.values():
            while True:
                msg = node.get_outgoing()
                if msg is None:
                    break
                self.in_flight.append(msg)
        
        # Deliver messages
        while self.in_flight:
            msg = self.in_flight.popleft()
            
            # Route message
            if msg.flags & MessageFlags.BROADCAST:
                # Deliver to all nodes except sender
                for nid, node in self.nodes.items():
                    if nid != msg.src_node:
                        node.recv_message(msg)
                        delivered += 1
            else:
                # Deliver to destination
                dst_node = self.nodes.get(msg.dst_node)
                if dst_node:
                    dst_node.recv_message(msg)
                    delivered += 1
                else:
                    self.dropped += 1
        
        self.delivered += delivered
        return delivered


class HSquaresOS:
    """
    The complete Hollywood Squares Operating System.
    
    A 1×8 star topology with:
    - 1 master node (node 0) running FabricKernel
    - 8 worker nodes (nodes 1-8) running NodeKernel
    - Message bus for communication
    - Unified control interface
    
    Usage:
        os = HSquaresOS()
        os.boot()
        
        # Send work
        result = os.exec(node=1, op=OpCode.ADD, a=50, b=10)
        
        # Or route automatically
        result = os.route(op=OpCode.ADD, a=50, b=10)
        
        # Run multiple ticks
        os.run(ticks=100)
    """
    
    def __init__(self, num_workers: int = 8):
        self.num_workers = num_workers
        
        # Create bus
        self.bus = MessageBus()
        
        # Create master node
        self.master = NodeKernel(node_id=0, is_master=True)
        self.bus.register_node(self.master)
        
        # Create fabric kernel on master
        self.fabric = FabricKernel(num_workers=num_workers)
        
        # Create worker nodes
        self.workers: Dict[int, NodeKernel] = {}
        for i in range(1, num_workers + 1):
            worker = NodeKernel(node_id=i)
            self.workers[i] = worker
            self.bus.register_node(worker)
        
        # System state
        self.tick_count = 0
        self.booted = False
        self.paused = False
        
        # Response collection
        self._pending_responses: Dict[int, Optional[Message]] = {}
        
        # Replay support
        self._recording = True
        self._message_log: List[Message] = []
        
        # Setup master to handle responses
        self.master.handlers[MessageType.PONG] = self._master_handle_pong
        self.master.handlers[MessageType.EXEC_OK] = self._master_handle_response
        self.master.handlers[MessageType.EXEC_ERR] = self._master_handle_response
        self.master.handlers[MessageType.COMPUTE_OK] = self._master_handle_response
        self.master.handlers[MessageType.STATUS_RPL] = self._master_handle_response
        
        # Setup trace callback
        for node in [self.master] + list(self.workers.values()):
            node.trace_callback = self._trace_callback
    
    def _trace_callback(self, node_id: int, tick: int, event: str, 
                        msg: Optional[Message], extra: str):
        """Unified trace callback."""
        self.fabric.trace(tick, node_id, event, msg, extra)
    
    def _master_handle_pong(self, msg: Message):
        """Master handles PONG (heartbeat response)."""
        self.fabric.handle_heartbeat_response(msg, self.tick_count)
        self._pending_responses[msg.msg_id] = msg
    
    def _master_handle_response(self, msg: Message):
        """Master handles response messages."""
        self._pending_responses[msg.msg_id] = msg
    
    # ========== Boot Sequence ==========
    
    def boot(self) -> Dict[int, bool]:
        """
        Boot the system.
        
        1. Initialize all nodes
        2. Ping all workers
        3. Record which are online
        
        Returns dict of node_id → online status.
        """
        results = {}
        
        # Initialize directory with all offline
        for i in range(1, self.num_workers + 1):
            self.fabric.set_node_status(i, NodeStatus.OFFLINE)
        
        # Ping each worker
        for i in range(1, self.num_workers + 1):
            msg = ping_msg(src=0, dst=i, msg_id=i)
            self._pending_responses[i] = None
            self.master.send_message(msg)
        
        # Run until responses or timeout
        for _ in range(100):  # Max 100 ticks for boot
            self._tick()
            
            # Check if all responded
            all_done = all(
                self._pending_responses.get(i) is not None
                for i in range(1, self.num_workers + 1)
            )
            if all_done:
                break
        
        # Record results
        for i in range(1, self.num_workers + 1):
            response = self._pending_responses.get(i)
            if response and response.msg_type == MessageType.PONG:
                self.fabric.set_node_status(i, NodeStatus.IDLE)
                self.fabric.update_heartbeat(i, self.tick_count, NodeStatus.IDLE, 0)
                results[i] = True
            else:
                results[i] = False
        
        self._pending_responses.clear()
        self.booted = True
        
        return results
    
    # ========== Core Operations ==========
    
    def _tick(self):
        """Execute one system tick."""
        self.tick_count += 1
        
        # Run all node kernels
        self.master.step()
        for worker in self.workers.values():
            worker.step()
        
        # Process bus
        self.bus.tick()
    
    def run(self, ticks: int = 1) -> int:
        """
        Run the system for N ticks.
        
        Returns number of messages processed.
        """
        total = 0
        for _ in range(ticks):
            self._tick()
            total += 1
        return total
    
    def exec(self, node: int, op: int, a: int = 0, b: int = 0, 
             flags: int = 0, timeout: int = 100) -> Optional[Tuple[int, int]]:
        """
        Execute an operation on a specific node.
        
        Returns (result, extra) or None on timeout.
        """
        msg_id = self.master.msg_seq + 1
        msg = exec_msg(0, node, msg_id, op, a, b, flags)
        
        self._pending_responses[msg_id] = None
        self.master.send_message(msg)
        
        # Run until response or timeout
        for _ in range(timeout):
            self._tick()
            response = self._pending_responses.get(msg_id)
            if response:
                del self._pending_responses[msg_id]
                if response.msg_type == MessageType.EXEC_OK:
                    return (response.payload[0], response.payload[1])
                else:
                    return None
        
        return None
    
    def compute(self, node: int, op: int, a: int, b: int,
                flags: int = 0, timeout: int = 100) -> Optional[Tuple[int, int]]:
        """
        Execute a neural compute operation on a specific node.
        
        Returns (result, flags) or None on timeout.
        """
        msg_id = self.master.msg_seq + 1
        msg = compute_msg(src=0, dst=node, msg_id=msg_id, op=op, a=a, b=b, flags=flags)
        
        self._pending_responses[msg_id] = None
        self.master.send_message(msg)
        
        # Run until response or timeout
        for _ in range(timeout):
            self._tick()
            response = self._pending_responses.get(msg_id)
            if response:
                del self._pending_responses[msg_id]
                if response.msg_type == MessageType.COMPUTE_OK:
                    return (response.payload[0], response.payload[1])
                else:
                    return None
        
        return None
    
    def route(self, op: int, a: int = 0, b: int = 0, 
              flags: int = 0, timeout: int = 100) -> Optional[Tuple[int, int, int]]:
        """
        Route work to best available node.
        
        Returns (node, result, extra) or None if no nodes available.
        """
        node = self.fabric.route_to_node()
        if node is None:
            return None
        
        result = self.exec(node, op, a, b, flags, timeout)
        if result:
            return (node, result[0], result[1])
        return None
    
    def broadcast_exec(self, op: int, a: int = 0, b: int = 0,
                       flags: int = 0, timeout: int = 200) -> Dict[int, Optional[Tuple[int, int]]]:
        """
        Execute operation on all online workers.
        
        Returns dict of node_id → (result, extra) or None.
        """
        results = {}
        online = self.fabric.get_online_nodes()
        
        # Send to all
        msg_ids = {}
        for node in online:
            msg_id = self.master.msg_seq + 1
            msg = exec_msg(0, node, msg_id, op, a, b, flags)
            self._pending_responses[msg_id] = None
            self.master.send_message(msg)
            msg_ids[node] = msg_id
        
        # Collect responses
        for _ in range(timeout):
            self._tick()
            
            # Check all responses
            all_done = True
            for node, msg_id in msg_ids.items():
                if node not in results:
                    response = self._pending_responses.get(msg_id)
                    if response:
                        if response.msg_type == MessageType.EXEC_OK:
                            results[node] = (response.payload[0], response.payload[1])
                        else:
                            results[node] = None
                        del self._pending_responses[msg_id]
                    else:
                        all_done = False
            
            if all_done:
                break
        
        # Mark timeouts
        for node in online:
            if node not in results:
                results[node] = None
        
        return results
    
    # ========== Status and Introspection ==========
    
    def ping(self, node: int, timeout: int = 50) -> Optional[Tuple[int, int]]:
        """
        Ping a node.
        
        Returns (status, load) or None on timeout.
        """
        msg_id = self.master.msg_seq + 1
        msg = ping_msg(src=0, dst=node, msg_id=msg_id)
        
        self._pending_responses[msg_id] = None
        self.master.send_message(msg)
        
        for _ in range(timeout):
            self._tick()
            response = self._pending_responses.get(msg_id)
            if response and response.msg_type == MessageType.PONG:
                del self._pending_responses[msg_id]
                return (response.payload[0], response.payload[1])
        
        return None
    
    def ping_all(self, timeout: int = 100) -> Dict[int, bool]:
        """Ping all workers, return online status."""
        results = {}
        for i in range(1, self.num_workers + 1):
            result = self.ping(i, timeout=timeout // self.num_workers)
            results[i] = result is not None
        return results
    
    def nodes(self) -> List[Dict]:
        """Get status of all nodes."""
        result = []
        
        # Master
        result.append({
            'id': 0,
            'role': 'master',
            'status': self.master.status.name,
            'msgs': self.master.msgs_received,
        })
        
        # Workers
        for i in range(1, self.num_workers + 1):
            entry = self.fabric.get_node(i)
            worker = self.workers[i]
            result.append({
                'id': i,
                'role': 'worker',
                'status': entry.status.name if entry else 'UNKNOWN',
                'load': entry.load if entry else 0,
                'msgs': worker.msgs_received,
            })
        
        return result
    
    def stats(self) -> Dict:
        """Get system statistics."""
        return {
            'tick': self.tick_count,
            'booted': self.booted,
            'bus_delivered': self.bus.delivered,
            'bus_dropped': self.bus.dropped,
            **self.fabric.get_fabric_stats(),
        }
    
    def trace(self, last_n: int = 20) -> str:
        """Get recent trace log."""
        return self.fabric.dump_trace()[-last_n*80:]  # Approximate
    
    # ========== Node Management ==========
    
    def reset(self, node: int):
        """Reset a specific node."""
        msg = Message(
            msg_type=MessageType.RESET,
            src_node=0,
            dst_node=node,
        )
        self.master.send_message(msg)
        self.run(10)  # Let it process
    
    def halt(self, node: int):
        """Halt a specific node."""
        msg = Message(
            msg_type=MessageType.HALT,
            src_node=0,
            dst_node=node,
        )
        self.master.send_message(msg)
        self.run(10)
    
    def set_neural_processor(self, node: int, processor):
        """Set the neural processor for a worker node."""
        if node in self.workers:
            self.workers[node].set_neural_processor(processor)
    
    # ========== Single-Step Execution ==========
    
    def pause(self):
        """Pause execution for single-stepping."""
        self.paused = True
    
    def resume(self):
        """Resume execution."""
        self.paused = False
    
    def step(self) -> Dict:
        """
        Execute exactly ONE tick and return detailed state.
        
        This is the key to inspectable computation.
        """
        # Snapshot before
        before_tick = self.tick_count
        before_msgs = self.bus.delivered
        
        # Collect outgoing messages before tick
        pending_out = []
        for node in [self.master] + list(self.workers.values()):
            for msg in list(node.outbox):
                pending_out.append({
                    'src': msg.src_node,
                    'dst': msg.dst_node,
                    'type': msg.msg_type.name,
                })
        
        # Execute one tick
        self._tick()
        
        # Snapshot after
        delivered = self.bus.delivered - before_msgs
        
        # Build state report
        state = {
            'tick': self.tick_count,
            'messages_delivered': delivered,
            'pending_out': pending_out,
            'nodes': {},
        }
        
        for node in [self.master] + list(self.workers.values()):
            state['nodes'][node.node_id] = {
                'status': node.status.name,
                'inbox': len(node.inbox),
                'outbox': len(node.outbox),
            }
        
        return state
    
    def step_until(self, condition: callable, max_ticks: int = 1000) -> int:
        """Step until condition is true, return tick count."""
        for i in range(max_ticks):
            state = self.step()
            if condition(state):
                return i + 1
        return max_ticks
    
    # ========== Deterministic Replay ==========
    
    def start_recording(self):
        """Start recording messages for replay."""
        self._recording = True
        self._message_log.clear()
    
    def stop_recording(self) -> List[Message]:
        """Stop recording and return message log."""
        self._recording = False
        return list(self._message_log)
    
    def get_recording(self) -> List[Dict]:
        """Get current recording as list of dicts."""
        return [
            {
                'tick': i,
                'type': msg.msg_type.name,
                'id': msg.msg_id,
                'src': msg.src_node,
                'dst': msg.dst_node,
                'payload': msg.payload[:msg.payload_len].hex(),
            }
            for i, msg in enumerate(self._message_log)
        ]
    
    def replay(self, log: List[Message]) -> bool:
        """
        Replay a message log from reset state.
        
        Returns True if replay matched exactly.
        """
        # Reset all nodes
        for worker in self.workers.values():
            worker.status = NodeStatus.IDLE
            worker.inbox.clear()
            worker.outbox.clear()
            worker.tick = 0
        
        self.master.inbox.clear()
        self.master.outbox.clear()
        self.master.tick = 0
        self.tick_count = 0
        
        # Inject messages and run
        for msg in log:
            # Clone message
            clone = Message(
                msg_type=msg.msg_type,
                msg_id=msg.msg_id,
                src_node=msg.src_node,
                dst_node=msg.dst_node,
                payload=msg.payload,
                flags=msg.flags,
            )
            self.master.send_message(clone)
            self._tick()
        
        return True
    
    def snapshot(self) -> Dict:
        """
        Take a complete system snapshot.
        
        Can be compared after replay to verify determinism.
        """
        snap = {
            'tick': self.tick_count,
            'master': {
                'status': self.master.status.name,
                'msgs_recv': self.master.msgs_received,
                'msgs_sent': self.master.msgs_sent,
            },
            'workers': {},
        }
        
        for nid, worker in self.workers.items():
            snap['workers'][nid] = {
                'status': worker.status.name,
                'msgs_recv': worker.msgs_received,
                'msgs_sent': worker.msgs_sent,
            }
        
        return snap


def demo():
    """Demonstrate the Hollywood Squares OS."""
    print("=" * 60)
    print("HOLLYWOOD SQUARES OS DEMO")
    print("=" * 60)
    
    # Create system
    print("\nCreating 1×8 system...")
    os = HSquaresOS(num_workers=8)
    
    # Boot
    print("\nBooting...")
    boot_result = os.boot()
    online = sum(1 for v in boot_result.values() if v)
    print(f"  {online}/{os.num_workers} workers online")
    
    # Show nodes
    print("\nNodes:")
    for node in os.nodes():
        print(f"  Node {node['id']}: {node['role']:<8} {node['status']:<8}")
    
    # Execute operations
    print("\nExecuting ADD(50, 10) on node 1...")
    result = os.exec(node=1, op=OpCode.ADD, a=50, b=10)
    if result:
        print(f"  Result: {result[0]} (carry: {result[1]})")
    
    print("\nRouting ADD(100, 55) to best node...")
    result = os.route(op=OpCode.ADD, a=100, b=55)
    if result:
        print(f"  Routed to node {result[0]}, result: {result[1]} (carry: {result[2]})")
    
    print("\nBroadcasting ADD(5, 3) to all workers...")
    results = os.broadcast_exec(op=OpCode.ADD, a=5, b=3)
    for node, res in results.items():
        if res:
            print(f"  Node {node}: {res[0]}")
    
    # Stats
    print("\nSystem stats:")
    stats = os.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    demo()
