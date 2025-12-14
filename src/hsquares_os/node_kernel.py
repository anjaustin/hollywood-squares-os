"""
NODE KERNEL

The node kernel runs on every 6502 in the system (master and workers).

Provides:
- Mailbox (incoming/outgoing queues)
- Dispatcher (route messages to handlers)
- Scheduler (cooperative, deterministic)
- Memory services
- Timers
- Introspection

The main loop is an interrupt-less event loop:
  wait for message → handle message → send response → repeat
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any, Tuple
from enum import IntEnum
from collections import deque
import time

from .message import Message, MessageType, MessageFlags, pong_msg, exec_ok_msg


class NodeStatus(IntEnum):
    """Node status codes."""
    OFFLINE = 0x00
    IDLE = 0x01
    BUSY = 0x02
    ERROR = 0x03
    HALTED = 0x04


class OpCode(IntEnum):
    """Built-in operation codes for EXEC messages."""
    NOP = 0x00
    ADD = 0x01          # Add two values
    SUB = 0x02          # Subtract
    CMP = 0x03          # Compare
    AND = 0x04          # Logical AND
    OR = 0x05           # Logical OR
    XOR = 0x06          # Logical XOR
    SHIFT_L = 0x07      # Shift left
    SHIFT_R = 0x08      # Shift right
    
    # Neural operations (use Spline-6502 organs)
    NEURAL_ALU = 0x10   # Neural ALU operation
    NEURAL_CMP = 0x11   # Neural compare
    NEURAL_LOGIC = 0x12 # Neural logic
    
    # Memory operations
    PEEK = 0x20         # Read memory
    POKE = 0x21         # Write memory
    COPY = 0x22         # Copy block
    
    # Custom handler registration
    CUSTOM = 0x80       # Custom handler (ID in next byte)


@dataclass
class NodeKernel:
    """
    The kernel that runs on every node.
    
    This is the core of the Hollywood Squares OS. Each node runs
    one of these, handling messages and dispatching to handlers.
    """
    
    node_id: int
    is_master: bool = False
    
    # State
    status: NodeStatus = NodeStatus.IDLE
    msg_seq: int = 0
    tick: int = 0
    error_code: int = 0
    
    # Memory (simulated 64KB)
    memory: bytearray = field(default_factory=lambda: bytearray(65536))
    
    # Message queues
    inbox: deque = field(default_factory=lambda: deque(maxlen=16))
    outbox: deque = field(default_factory=lambda: deque(maxlen=16))
    
    # Pending responses (msg_id → callback)
    pending: Dict[int, Callable] = field(default_factory=dict)
    
    # Handler table (opcode → handler function)
    handlers: Dict[int, Callable] = field(default_factory=dict)
    
    # Statistics
    msgs_received: int = 0
    msgs_sent: int = 0
    errors: int = 0
    
    # Neural processor reference (optional)
    neural_processor: Any = None
    
    # Trace callback (optional)
    trace_callback: Optional[Callable] = None
    
    def __post_init__(self):
        """Initialize kernel."""
        self._register_builtin_handlers()
    
    def _register_builtin_handlers(self):
        """Register built-in message handlers."""
        # System handlers
        self.handlers[MessageType.PING] = self._handle_ping
        self.handlers[MessageType.PONG] = self._handle_pong
        self.handlers[MessageType.EXEC] = self._handle_exec
        self.handlers[MessageType.EXEC_OK] = self._handle_response
        self.handlers[MessageType.EXEC_ERR] = self._handle_response
        self.handlers[MessageType.RESET] = self._handle_reset
        self.handlers[MessageType.STATUS] = self._handle_status
        self.handlers[MessageType.HALT] = self._handle_halt
        self.handlers[MessageType.COMPUTE] = self._handle_compute
        self.handlers[MessageType.COMPUTE_OK] = self._handle_response
        
        # Operation handlers
        self._op_handlers = {
            OpCode.NOP: lambda a, b, f: (0, 0),
            OpCode.ADD: lambda a, b, f: ((a + b) & 0xFF, int((a + b) > 255)),
            OpCode.SUB: lambda a, b, f: ((a - b) & 0xFF, int(a < b)),
            OpCode.CMP: lambda a, b, f: (int(a == b), int(a < b) | (int(a > b) << 1)),
            OpCode.AND: lambda a, b, f: (a & b, 0),
            OpCode.OR: lambda a, b, f: (a | b, 0),
            OpCode.XOR: lambda a, b, f: (a ^ b, 0),
            OpCode.SHIFT_L: lambda a, b, f: ((a << 1) & 0xFF, (a >> 7) & 1),
            OpCode.SHIFT_R: lambda a, b, f: (a >> 1, a & 1),
        }
    
    def register_handler(self, opcode: int, handler: Callable):
        """Register a custom operation handler."""
        self._op_handlers[opcode] = handler
    
    def set_neural_processor(self, processor):
        """Set the neural processor for COMPUTE operations."""
        self.neural_processor = processor
    
    # ========== Message Handling ==========
    
    def recv_message(self, msg: Message):
        """Receive a message into the inbox."""
        if len(self.inbox) < self.inbox.maxlen:
            self.inbox.append(msg)
            self.msgs_received += 1
            self._trace('RECV', msg)
        else:
            self.errors += 1
            self._trace('OVERFLOW', msg)
    
    def send_message(self, msg: Message):
        """Queue a message for sending."""
        msg.src_node = self.node_id
        self.outbox.append(msg)
        self.msgs_sent += 1
        self._trace('SEND', msg)
    
    def get_outgoing(self) -> Optional[Message]:
        """Get next message to send (called by bus)."""
        if self.outbox:
            return self.outbox.popleft()
        return None
    
    def has_pending_messages(self) -> bool:
        """Check if there are messages to process."""
        return len(self.inbox) > 0
    
    # ========== Main Loop ==========
    
    def step(self) -> bool:
        """
        Execute one kernel step.
        
        Returns True if work was done, False if idle.
        """
        self.tick += 1
        
        # Check inbox
        if self.inbox:
            msg = self.inbox.popleft()
            self._dispatch(msg)
            return True
        
        return False
    
    def run(self, max_ticks: int = 1000) -> int:
        """
        Run kernel for up to max_ticks.
        
        Returns number of messages processed.
        """
        processed = 0
        for _ in range(max_ticks):
            if self.status == NodeStatus.HALTED:
                break
            if self.step():
                processed += 1
        return processed
    
    def _dispatch(self, msg: Message):
        """Dispatch message to appropriate handler."""
        handler = self.handlers.get(msg.msg_type)
        
        if handler:
            try:
                self.status = NodeStatus.BUSY
                handler(msg)
                self.status = NodeStatus.IDLE
            except Exception as e:
                self.status = NodeStatus.ERROR
                self.error_code = 0xFF
                self.errors += 1
                self._trace('ERROR', msg, str(e))
        else:
            # Unknown message type
            self.errors += 1
            self._trace('UNKNOWN', msg)
    
    # ========== Built-in Handlers ==========
    
    def _handle_ping(self, msg: Message):
        """Handle PING - respond with PONG."""
        response = pong_msg(
            src=self.node_id,
            dst=msg.src_node,
            msg_id=msg.msg_id,
            status=int(self.status),
            load=len(self.inbox),
        )
        self.send_message(response)
    
    def _handle_pong(self, msg: Message):
        """Handle PONG - complete pending request."""
        self._complete_pending(msg)
    
    def _handle_exec(self, msg: Message):
        """Handle EXEC - execute operation and respond."""
        payload = msg.payload
        opcode = payload[0] if len(payload) > 0 else 0
        a = payload[1] if len(payload) > 1 else 0
        b = payload[2] if len(payload) > 2 else 0
        flags = payload[3] if len(payload) > 3 else 0
        
        # Find handler
        handler = self._op_handlers.get(opcode)
        
        if handler:
            result, extra = handler(a, b, flags)
            response = exec_ok_msg(
                self.node_id,
                msg.src_node,
                msg.msg_id,
                result, extra,
            )
        else:
            # Unknown opcode
            response = Message(
                msg_type=MessageType.EXEC_ERR,
                msg_id=msg.msg_id,
                src_node=self.node_id,
                dst_node=msg.src_node,
                payload=bytes([0x01]),  # Error code: unknown opcode
            )
        
        self.send_message(response)
    
    def _handle_compute(self, msg: Message):
        """Handle COMPUTE - neural operation."""
        payload = msg.payload
        op = payload[0] if len(payload) > 0 else 0
        a = payload[1] if len(payload) > 1 else 0
        b = payload[2] if len(payload) > 2 else 0
        flags = payload[3] if len(payload) > 3 else 0
        
        if self.neural_processor:
            # Use neural processor
            try:
                result, out_flags = self.neural_processor.compute(op, a, b, flags)
                response = Message(
                    msg_type=MessageType.COMPUTE_OK,
                    msg_id=msg.msg_id,
                    src_node=self.node_id,
                    dst_node=msg.src_node,
                    payload=bytes([result, out_flags]),
                )
            except Exception as e:
                response = Message(
                    msg_type=MessageType.EXEC_ERR,
                    msg_id=msg.msg_id,
                    src_node=self.node_id,
                    dst_node=msg.src_node,
                    payload=bytes([0x02]),  # Error: compute failed
                )
        else:
            # Fallback to standard ops
            handler = self._op_handlers.get(op)
            if handler:
                result, extra = handler(a, b, flags)
                response = Message(
                    msg_type=MessageType.COMPUTE_OK,
                    msg_id=msg.msg_id,
                    src_node=self.node_id,
                    dst_node=msg.src_node,
                    payload=bytes([result, extra]),
                )
            else:
                response = Message(
                    msg_type=MessageType.EXEC_ERR,
                    msg_id=msg.msg_id,
                    src_node=self.node_id,
                    dst_node=msg.src_node,
                    payload=bytes([0x01]),
                )
        
        self.send_message(response)
    
    def _handle_response(self, msg: Message):
        """Handle response messages (EXEC_OK, PONG, etc.)."""
        self._complete_pending(msg)
    
    def _handle_reset(self, msg: Message):
        """Handle RESET - reinitialize node."""
        self.status = NodeStatus.IDLE
        self.error_code = 0
        self.inbox.clear()
        # Don't clear outbox - may need to send response
        self._trace('RESET', msg)
    
    def _handle_status(self, msg: Message):
        """Handle STATUS request."""
        response = Message(
            msg_type=MessageType.STATUS_RPL,
            msg_id=msg.msg_id,
            src_node=self.node_id,
            dst_node=msg.src_node,
            payload=bytes([
                int(self.status),
                len(self.inbox),
                len(self.outbox),
                self.error_code,
                self.msgs_received & 0xFF,
                self.msgs_sent & 0xFF,
                self.errors & 0xFF,
            ]),
        )
        self.send_message(response)
    
    def _handle_halt(self, msg: Message):
        """Handle HALT - stop processing."""
        self.status = NodeStatus.HALTED
        self._trace('HALT', msg)
    
    # ========== Async Request/Response ==========
    
    def send_request(self, msg: Message, callback: Optional[Callable] = None) -> int:
        """
        Send a request message and optionally register callback for response.
        
        Returns the msg_id for tracking.
        """
        self.msg_seq = (self.msg_seq + 1) & 0xFF
        msg.msg_id = self.msg_seq
        
        if callback:
            self.pending[msg.msg_id] = callback
        
        self.send_message(msg)
        return msg.msg_id
    
    def _complete_pending(self, msg: Message):
        """Complete a pending request with its response."""
        callback = self.pending.pop(msg.msg_id, None)
        if callback:
            callback(msg)
    
    # ========== Memory Operations ==========
    
    def peek(self, addr: int) -> int:
        """Read byte from memory."""
        return self.memory[addr & 0xFFFF]
    
    def poke(self, addr: int, value: int):
        """Write byte to memory."""
        self.memory[addr & 0xFFFF] = value & 0xFF
    
    def peek_word(self, addr: int) -> int:
        """Read 16-bit word from memory (little-endian)."""
        lo = self.memory[addr & 0xFFFF]
        hi = self.memory[(addr + 1) & 0xFFFF]
        return lo | (hi << 8)
    
    def poke_word(self, addr: int, value: int):
        """Write 16-bit word to memory (little-endian)."""
        self.memory[addr & 0xFFFF] = value & 0xFF
        self.memory[(addr + 1) & 0xFFFF] = (value >> 8) & 0xFF
    
    # ========== Tracing ==========
    
    def _trace(self, event: str, msg: Optional[Message] = None, extra: str = ''):
        """Record a trace event."""
        if self.trace_callback:
            self.trace_callback(self.node_id, self.tick, event, msg, extra)
    
    # ========== Introspection ==========
    
    def get_stats(self) -> Dict:
        """Get kernel statistics."""
        return {
            'node_id': self.node_id,
            'status': self.status.name,
            'tick': self.tick,
            'msgs_received': self.msgs_received,
            'msgs_sent': self.msgs_sent,
            'errors': self.errors,
            'inbox_depth': len(self.inbox),
            'outbox_depth': len(self.outbox),
            'pending_requests': len(self.pending),
        }
    
    def dump_state(self) -> Dict:
        """Dump complete kernel state for debugging."""
        return {
            **self.get_stats(),
            'msg_seq': self.msg_seq,
            'error_code': self.error_code,
            'inbox': [repr(m) for m in self.inbox],
            'outbox': [repr(m) for m in self.outbox],
        }
