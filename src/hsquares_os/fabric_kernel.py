"""
FABRIC KERNEL

The fabric kernel runs only on the master node (node 0).

Provides global services:
- Directory: name → node mapping, status tracking
- Router: dispatch work to available nodes
- Supervisor: health monitoring, restart, isolation
- Loader: program deployment
- Tracer: distributed event logging
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import IntEnum
import time

from .message import Message, MessageType, ping_msg, exec_msg, compute_msg
from .node_kernel import NodeKernel, NodeStatus


@dataclass
class NodeEntry:
    """Directory entry for a node."""
    node_id: int
    status: NodeStatus = NodeStatus.OFFLINE
    capabilities: int = 0xFF  # Bitmask of capabilities
    load: int = 0             # Current load (0-255)
    program_id: int = 0       # Currently loaded program
    last_heartbeat: int = 0   # Tick of last heartbeat
    msg_count: int = 0        # Messages processed
    error_count: int = 0      # Errors encountered


class Capability(IntEnum):
    """Node capability flags."""
    BASIC = 0x01        # Basic operations
    NEURAL_ALU = 0x02   # Neural ALU
    NEURAL_CMP = 0x04   # Neural compare
    NEURAL_LOGIC = 0x08 # Neural logic
    MEMORY = 0x10       # Extended memory
    CUSTOM = 0x80       # Custom handlers


@dataclass
class TraceEntry:
    """Entry in the trace log."""
    tick: int
    node_id: int
    event: str
    msg_type: Optional[str] = None
    msg_id: int = 0
    extra: str = ''


class FabricKernel:
    """
    The fabric kernel provides global services for the node network.
    
    Only runs on the master node. Other nodes run just the NodeKernel.
    """
    
    def __init__(self, num_workers: int = 8):
        self.num_workers = num_workers
        
        # Directory of all nodes
        self.directory: Dict[int, NodeEntry] = {}
        for i in range(1, num_workers + 1):
            self.directory[i] = NodeEntry(node_id=i)
        
        # Routing state
        self.round_robin_idx = 1
        
        # Supervisor state
        self.heartbeat_interval = 256
        self.heartbeat_timeout = 1024
        self.last_heartbeat_tick = 0
        
        # Trace log
        self.trace_log: List[TraceEntry] = []
        self.max_trace_entries = 1000
        
        # Pending heartbeats
        self.pending_heartbeats: Dict[int, int] = {}  # msg_id → node_id
        
        # Callbacks
        self.on_node_online: Optional[Callable] = None
        self.on_node_offline: Optional[Callable] = None
        self.on_node_error: Optional[Callable] = None
    
    # ========== Directory Service ==========
    
    def get_node(self, node_id: int) -> Optional[NodeEntry]:
        """Get directory entry for a node."""
        return self.directory.get(node_id)
    
    def set_node_status(self, node_id: int, status: NodeStatus):
        """Update node status."""
        entry = self.directory.get(node_id)
        if entry:
            old_status = entry.status
            entry.status = status
            
            # Trigger callbacks on status change
            if old_status != status:
                if status == NodeStatus.OFFLINE and self.on_node_offline:
                    self.on_node_offline(node_id)
                elif status != NodeStatus.OFFLINE and old_status == NodeStatus.OFFLINE:
                    if self.on_node_online:
                        self.on_node_online(node_id)
                elif status == NodeStatus.ERROR and self.on_node_error:
                    self.on_node_error(node_id)
    
    def update_heartbeat(self, node_id: int, tick: int, status: int, load: int):
        """Update node heartbeat info."""
        entry = self.directory.get(node_id)
        if entry:
            entry.last_heartbeat = tick
            entry.status = NodeStatus(status) if status in NodeStatus._value2member_map_ else NodeStatus.IDLE
            entry.load = load
    
    def get_online_nodes(self) -> List[int]:
        """Get list of online node IDs."""
        return [
            nid for nid, entry in self.directory.items()
            if entry.status not in (NodeStatus.OFFLINE, NodeStatus.HALTED)
        ]
    
    def get_available_nodes(self) -> List[int]:
        """Get list of available (online and not busy) nodes."""
        return [
            nid for nid, entry in self.directory.items()
            if entry.status == NodeStatus.IDLE
        ]
    
    # ========== Router Service ==========
    
    def route_to_node(self, work_type: int = 0) -> Optional[int]:
        """
        Select a node to route work to.
        
        Uses load-aware routing: picks the least loaded available node.
        Falls back to round-robin if loads are equal.
        """
        available = self.get_available_nodes()
        if not available:
            return None
        
        # Find least loaded
        min_load = 256
        best_node = None
        
        for nid in available:
            entry = self.directory[nid]
            if entry.load < min_load:
                min_load = entry.load
                best_node = nid
        
        # If all equal load, use round robin
        if best_node is None or all(
            self.directory[nid].load == min_load for nid in available
        ):
            # Round robin among available
            for _ in range(self.num_workers):
                self.round_robin_idx = (self.round_robin_idx % self.num_workers) + 1
                if self.round_robin_idx in available:
                    return self.round_robin_idx
        
        return best_node
    
    def route_to_capable(self, capability: Capability) -> Optional[int]:
        """Select a node with specific capability."""
        available = self.get_available_nodes()
        capable = [
            nid for nid in available
            if self.directory[nid].capabilities & capability
        ]
        
        if not capable:
            return None
        
        # Least loaded among capable
        min_load = 256
        best = capable[0]
        for nid in capable:
            if self.directory[nid].load < min_load:
                min_load = self.directory[nid].load
                best = nid
        
        return best
    
    def broadcast(self) -> List[int]:
        """Get all online nodes for broadcast."""
        return self.get_online_nodes()
    
    # ========== Supervisor Service ==========
    
    def supervisor_tick(self, current_tick: int, send_fn: Callable[[Message], int]) -> List[Message]:
        """
        Run supervisor tick.
        
        - Send heartbeats if interval elapsed
        - Check for timed out nodes
        
        Returns list of messages to send.
        """
        messages = []
        
        # Check for timeouts
        for nid, entry in self.directory.items():
            if entry.status not in (NodeStatus.OFFLINE, NodeStatus.HALTED):
                age = current_tick - entry.last_heartbeat
                if age > self.heartbeat_timeout:
                    # Node timed out
                    self.set_node_status(nid, NodeStatus.OFFLINE)
                    self.trace(current_tick, nid, 'TIMEOUT')
        
        # Send heartbeats if interval elapsed
        if current_tick - self.last_heartbeat_tick >= self.heartbeat_interval:
            self.last_heartbeat_tick = current_tick
            
            for nid in self.get_online_nodes():
                msg = ping_msg(src=0, dst=nid)
                msg_id = send_fn(msg)
                self.pending_heartbeats[msg_id] = nid
        
        return messages
    
    def handle_heartbeat_response(self, msg: Message, tick: int):
        """Handle PONG response from heartbeat."""
        node_id = self.pending_heartbeats.pop(msg.msg_id, None)
        if node_id is not None:
            status = msg.payload[0] if len(msg.payload) > 0 else 0
            load = msg.payload[1] if len(msg.payload) > 1 else 0
            self.update_heartbeat(node_id, tick, status, load)
    
    def reset_node(self, node_id: int) -> Message:
        """Create a RESET message for a node."""
        return Message(
            msg_type=MessageType.RESET,
            src_node=0,
            dst_node=node_id,
        )
    
    def quarantine_node(self, node_id: int):
        """Quarantine a misbehaving node."""
        entry = self.directory.get(node_id)
        if entry:
            entry.status = NodeStatus.ERROR
            entry.error_count += 1
            self.trace(0, node_id, 'QUARANTINE')
    
    # ========== Loader Service ==========
    
    def load_program(self, node_id: int, program_id: int, program_data: bytes) -> List[Message]:
        """
        Create messages to load a program onto a node.
        
        For now, just sets the program_id. Full implementation would
        send LOAD messages with program chunks.
        """
        entry = self.directory.get(node_id)
        if entry:
            entry.program_id = program_id
        
        # In full implementation, would return LOAD messages
        return [
            Message(
                msg_type=MessageType.LOAD,
                src_node=0,
                dst_node=node_id,
                payload=bytes([program_id & 0xFF, (program_id >> 8) & 0xFF]),
            )
        ]
    
    # ========== Tracer Service ==========
    
    def trace(self, tick: int, node_id: int, event: str, 
              msg: Optional[Message] = None, extra: str = ''):
        """Add entry to trace log."""
        entry = TraceEntry(
            tick=tick,
            node_id=node_id,
            event=event,
            msg_type=msg.msg_type.name if msg else None,
            msg_id=msg.msg_id if msg else 0,
            extra=extra,
        )
        
        self.trace_log.append(entry)
        
        # Trim if too long
        if len(self.trace_log) > self.max_trace_entries:
            self.trace_log = self.trace_log[-self.max_trace_entries:]
    
    def get_trace(self, last_n: int = 100) -> List[TraceEntry]:
        """Get recent trace entries."""
        return self.trace_log[-last_n:]
    
    def dump_trace(self) -> str:
        """Dump trace log as string."""
        lines = []
        for entry in self.trace_log:
            line = f"[{entry.tick:6d}] Node {entry.node_id}: {entry.event}"
            if entry.msg_type:
                line += f" ({entry.msg_type} #{entry.msg_id})"
            if entry.extra:
                line += f" - {entry.extra}"
            lines.append(line)
        return "\n".join(lines)
    
    # ========== Introspection ==========
    
    def get_directory_summary(self) -> Dict:
        """Get summary of all nodes."""
        summary = {}
        for nid, entry in self.directory.items():
            summary[nid] = {
                'status': entry.status.name,
                'load': entry.load,
                'program': entry.program_id,
                'msgs': entry.msg_count,
                'errors': entry.error_count,
            }
        return summary
    
    def get_fabric_stats(self) -> Dict:
        """Get fabric-level statistics."""
        online = len(self.get_online_nodes())
        available = len(self.get_available_nodes())
        total_msgs = sum(e.msg_count for e in self.directory.values())
        total_errors = sum(e.error_count for e in self.directory.values())
        
        return {
            'total_nodes': self.num_workers,
            'online_nodes': online,
            'available_nodes': available,
            'total_messages': total_msgs,
            'total_errors': total_errors,
            'trace_entries': len(self.trace_log),
        }
