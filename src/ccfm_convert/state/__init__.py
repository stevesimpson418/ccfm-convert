"""State management for CCFM deployments."""

from .backend import ConfluenceBackend, StateBackend
from .init import init_remote_state
from .lock import LockError, LockInfo, LockManager
from .manager import StateManager

__all__ = [
    "ConfluenceBackend",
    "LockError",
    "LockInfo",
    "LockManager",
    "StateBackend",
    "StateManager",
    "init_remote_state",
]
