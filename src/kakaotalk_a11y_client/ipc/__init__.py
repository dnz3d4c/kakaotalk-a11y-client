"""IPC 모듈 - Tauri GUI와 Named Pipe 통신"""

from .server import IPCServer
from .protocol import JsonRpcMessage, JsonRpcError
from .handlers import create_handlers

__all__ = ["IPCServer", "JsonRpcMessage", "JsonRpcError", "create_handlers"]
