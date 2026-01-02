"""JSON-RPC 2.0 프로토콜 처리"""

from dataclasses import dataclass
from typing import Any, Optional
import json


class JsonRpcError(Exception):
    """JSON-RPC 에러"""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


# 표준 에러 코드
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class JsonRpcMessage:
    """JSON-RPC 메시지"""

    jsonrpc: str = "2.0"
    method: Optional[str] = None
    params: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[dict] = None
    id: Optional[int] = None

    @classmethod
    def from_json(cls, data: str) -> "JsonRpcMessage":
        """JSON 문자열에서 파싱"""
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as e:
            raise JsonRpcError(PARSE_ERROR, f"Parse error: {e}")

        if not isinstance(obj, dict):
            raise JsonRpcError(INVALID_REQUEST, "Request must be an object")

        return cls(
            jsonrpc=obj.get("jsonrpc", "2.0"),
            method=obj.get("method"),
            params=obj.get("params"),
            result=obj.get("result"),
            error=obj.get("error"),
            id=obj.get("id"),
        )

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        obj = {"jsonrpc": self.jsonrpc}

        if self.method is not None:
            obj["method"] = self.method
        if self.params is not None:
            obj["params"] = self.params
        if self.result is not None:
            obj["result"] = self.result
        if self.error is not None:
            obj["error"] = self.error
        if self.id is not None:
            obj["id"] = self.id

        return json.dumps(obj, ensure_ascii=False)

    @classmethod
    def success(cls, id: int, result: Any) -> "JsonRpcMessage":
        """성공 응답 생성"""
        return cls(id=id, result=result)

    @classmethod
    def error_response(cls, id: Optional[int], error: JsonRpcError) -> "JsonRpcMessage":
        """에러 응답 생성"""
        return cls(id=id, error=error.to_dict())

    @classmethod
    def notification(cls, method: str, params: Any = None) -> "JsonRpcMessage":
        """알림 메시지 생성 (id 없음)"""
        return cls(method=method, params=params)
