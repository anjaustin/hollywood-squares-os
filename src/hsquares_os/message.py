"""
MESSAGE FRAME

All communication in Hollywood Squares OS is via fixed-size messages.

Frame format (16 bytes):
  $00     msg_type      Message type code
  $01     msg_id        Sequence number
  $02     src_node      Source node ID
  $03     dst_node      Destination node ID
  $04     payload_len   Payload length (0-10)
  $05     flags         Flags
  $06-$0F payload       Message payload (10 bytes)
"""

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import List, Optional
import struct


class MessageType(IntEnum):
    """Message type codes."""
    NOP = 0x00         # No operation
    PING = 0x01        # Health check request
    PONG = 0x02        # Health check response
    EXEC = 0x03        # Execute handler
    EXEC_OK = 0x04     # Execution succeeded
    EXEC_ERR = 0x05    # Execution failed
    LOAD = 0x06        # Load program
    LOAD_OK = 0x07     # Load succeeded
    DUMP = 0x08        # Memory dump request
    DUMP_DATA = 0x09   # Memory dump response
    RESET = 0x0A       # Reset node
    TRACE = 0x0B       # Trace event
    ROUTE = 0x0C       # Route work
    STATUS = 0x0D      # Status request
    STATUS_RPL = 0x0E  # Status response
    HALT = 0x0F        # Halt node
    
    # Extended types for neural operations
    COMPUTE = 0x10     # Neural compute request
    COMPUTE_OK = 0x11  # Neural compute response
    
    @property
    def is_request(self) -> bool:
        """Is this a request type (expects response)?"""
        return self in (
            MessageType.PING,
            MessageType.EXEC,
            MessageType.LOAD,
            MessageType.DUMP,
            MessageType.STATUS,
            MessageType.ROUTE,
            MessageType.COMPUTE,
        )
    
    @property
    def response_type(self) -> Optional['MessageType']:
        """Get the expected response type for a request."""
        mapping = {
            MessageType.PING: MessageType.PONG,
            MessageType.EXEC: MessageType.EXEC_OK,
            MessageType.LOAD: MessageType.LOAD_OK,
            MessageType.DUMP: MessageType.DUMP_DATA,
            MessageType.STATUS: MessageType.STATUS_RPL,
            MessageType.COMPUTE: MessageType.COMPUTE_OK,
        }
        return mapping.get(self)


class MessageFlags(IntFlag):
    """Message flags."""
    NONE = 0x00
    ACK_REQ = 0x01     # Acknowledgment required
    PRIORITY = 0x02   # High priority
    FRAGMENT = 0x04   # Part of fragmented message
    LAST_FRAG = 0x08  # Last fragment
    BROADCAST = 0x10  # Send to all nodes


@dataclass
class Message:
    """
    Fixed-size message frame (16 bytes).
    
    This is the fundamental communication primitive in Hollywood Squares OS.
    All syscalls, all inter-node communication, all control - everything
    flows through messages.
    """
    msg_type: MessageType
    msg_id: int = 0
    src_node: int = 0
    dst_node: int = 0
    payload: bytes = field(default_factory=lambda: bytes(10))
    flags: MessageFlags = MessageFlags.NONE
    
    # Frame size
    FRAME_SIZE = 16
    PAYLOAD_SIZE = 10
    
    def __post_init__(self):
        # Ensure payload is correct size
        if len(self.payload) > self.PAYLOAD_SIZE:
            self.payload = self.payload[:self.PAYLOAD_SIZE]
        elif len(self.payload) < self.PAYLOAD_SIZE:
            self.payload = self.payload + bytes(self.PAYLOAD_SIZE - len(self.payload))
        
        # Ensure msg_type is MessageType enum
        if isinstance(self.msg_type, int):
            self.msg_type = MessageType(self.msg_type)
        
        # Ensure flags is MessageFlags enum
        if isinstance(self.flags, int):
            self.flags = MessageFlags(self.flags)
    
    @property
    def payload_len(self) -> int:
        """Length of meaningful payload data."""
        # Find last non-zero byte
        for i in range(len(self.payload) - 1, -1, -1):
            if self.payload[i] != 0:
                return i + 1
        return 0
    
    def to_bytes(self) -> bytes:
        """Serialize message to 16-byte frame."""
        return struct.pack(
            'BBBBBB10s',
            self.msg_type,
            self.msg_id & 0xFF,
            self.src_node & 0xFF,
            self.dst_node & 0xFF,
            self.payload_len,
            int(self.flags),
            self.payload,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """Deserialize message from 16-byte frame."""
        if len(data) < cls.FRAME_SIZE:
            data = data + bytes(cls.FRAME_SIZE - len(data))
        
        msg_type, msg_id, src, dst, plen, flags, payload = struct.unpack(
            'BBBBBB10s', data[:cls.FRAME_SIZE]
        )
        
        return cls(
            msg_type=MessageType(msg_type),
            msg_id=msg_id,
            src_node=src,
            dst_node=dst,
            payload=payload,
            flags=MessageFlags(flags),
        )
    
    def response(self, payload: bytes = b'', error: bool = False) -> 'Message':
        """Create a response to this message."""
        if error:
            resp_type = MessageType.EXEC_ERR
        elif self.msg_type.response_type:
            resp_type = self.msg_type.response_type
        else:
            resp_type = MessageType.NOP
        
        return Message(
            msg_type=resp_type,
            msg_id=self.msg_id,
            src_node=self.dst_node,
            dst_node=self.src_node,
            payload=payload,
        )
    
    def __repr__(self) -> str:
        return (
            f"Message({self.msg_type.name}, "
            f"id={self.msg_id}, "
            f"{self.src_node}→{self.dst_node}, "
            f"payload={self.payload[:self.payload_len].hex() or '(empty)'})"
        )


# Factory functions for common messages

def ping_msg(src: int, dst: int, msg_id: int = 0) -> Message:
    """Create a PING message."""
    return Message(
        msg_type=MessageType.PING,
        msg_id=msg_id,
        src_node=src,
        dst_node=dst,
        flags=MessageFlags.ACK_REQ,
    )


def pong_msg(src: int, dst: int, msg_id: int, status: int, load: int) -> Message:
    """Create a PONG response."""
    return Message(
        msg_type=MessageType.PONG,
        msg_id=msg_id,
        src_node=src,
        dst_node=dst,
        payload=bytes([status, load]),
    )


def exec_msg(src: int, dst: int, msg_id: int, handler_id: int, *args: int) -> Message:
    """Create an EXEC message."""
    payload = bytes([handler_id] + list(args)[:9])
    return Message(
        msg_type=MessageType.EXEC,
        msg_id=msg_id,
        src_node=src,
        dst_node=dst,
        payload=payload,
        flags=MessageFlags.ACK_REQ,
    )


def exec_ok_msg(src: int, dst: int, msg_id: int, *results: int) -> Message:
    """Create an EXEC_OK response."""
    return Message(
        msg_type=MessageType.EXEC_OK,
        msg_id=msg_id,
        src_node=src,
        dst_node=dst,
        payload=bytes(results[:10]),
    )


def compute_msg(src: int, dst: int, msg_id: int, op: int, a: int, b: int, flags: int = 0) -> Message:
    """Create a COMPUTE message for neural operations."""
    return Message(
        msg_type=MessageType.COMPUTE,
        msg_id=msg_id,
        src_node=src,
        dst_node=dst,
        payload=bytes([op, a, b, flags]),
        flags=MessageFlags.ACK_REQ,
    )


def trace_msg(src: int, event_type: int, *data: int) -> Message:
    """Create a TRACE message (fire-and-forget)."""
    return Message(
        msg_type=MessageType.TRACE,
        msg_id=0,
        src_node=src,
        dst_node=0,  # Always to master
        payload=bytes([event_type] + list(data)[:9]),
    )
