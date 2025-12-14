"""
HOLLYWOOD SQUARES OS

A distributed microkernel for addressable 6502 processors.

Architecture:
- Message passing as syscall interface
- Actors mapped to nodes
- Supervision trees for fault tolerance
- Deterministic replay for debugging

Components:
- NodeKernel: Runs on every node (mailbox, dispatcher, scheduler)
- FabricKernel: Runs on master (directory, router, supervisor)
- Message: Fixed-size message frame
- HSquaresOS: Complete 1×8 system
- SquaresShell: Bash-like interface (sqsh)
"""

from .message import Message, MessageType, MessageFlags
from .node_kernel import NodeKernel, NodeStatus, OpCode
from .fabric_kernel import FabricKernel
from .system import HSquaresOS
from .shell import SquaresShell
from .sorting_network import SortingNetwork
from .sorting_fabric import SortingFabric
from .bubble_machine import BubbleMachine
from .constraint_field import ConstraintField

__all__ = [
    'Message',
    'MessageType', 
    'MessageFlags',
    'NodeKernel',
    'NodeStatus',
    'OpCode',
    'FabricKernel',
    'HSquaresOS',
    'SquaresShell',
    'SortingNetwork',
    'SortingFabric',
    'BubbleMachine',
    'ConstraintField',
]
