from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from audio_mcp.audition.errors import AuditionError, ErrorCode


PROTOCOL = "audio-mcp-audition/1"
MAX_MESSAGE_BYTES = 65_536
MAX_TIMEOUT_MS = 60_000
OPERATION_PATTERN = re.compile(r"[a-z][a-z_]*")


def _protocol_error(message: str) -> AuditionError:
    return AuditionError(ErrorCode.PROTOCOL_ERROR, message)


@dataclass(frozen=True)
class Request:
    request_id: str
    operation: str
    arguments: dict[str, Any]
    deadline_ms: int

    @classmethod
    def create(
        cls,
        operation: str,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> Request:
        if (
            not isinstance(operation, str)
            or OPERATION_PATTERN.fullmatch(operation) is None
        ):
            raise AuditionError(
                ErrorCode.INVALID_ARGUMENT,
                "Operation must be a lowercase allowlisted identifier.",
            )
        if not isinstance(arguments, dict):
            raise AuditionError(
                ErrorCode.INVALID_ARGUMENT,
                "Operation arguments must be an object.",
            )
        if (
            isinstance(timeout_ms, bool)
            or not isinstance(timeout_ms, int)
            or not 1 <= timeout_ms <= MAX_TIMEOUT_MS
        ):
            raise AuditionError(
                ErrorCode.INVALID_ARGUMENT,
                "Timeout must be an integer from 1 to 60000 milliseconds.",
            )
        return cls(
            request_id=uuid.uuid4().hex,
            operation=operation,
            arguments=dict(arguments),
            deadline_ms=timeout_ms,
        )

    def to_json(self) -> str:
        try:
            payload = json.dumps(
                {
                    "protocol": PROTOCOL,
                    "request_id": self.request_id,
                    "operation": self.operation,
                    "arguments": self.arguments,
                    "deadline_ms": self.deadline_ms,
                },
                allow_nan=False,
                separators=(",", ":"),
            )
            size = len(payload.encode("utf-8"))
        except (TypeError, ValueError, UnicodeError):
            raise _protocol_error(
                "Request contains values that cannot be encoded safely."
            ) from None
        if size > MAX_MESSAGE_BYTES:
            raise _protocol_error("Request exceeds the 65536-byte protocol limit.")
        return payload


@dataclass(frozen=True)
class Response:
    request_id: str
    result: dict[str, Any]

    @classmethod
    def from_json(
        cls,
        payload: str,
        *,
        expected_request_id: str,
    ) -> Response:
        try:
            if len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES:
                raise _protocol_error(
                    "Response exceeds the 65536-byte protocol limit."
                )
            raw = json.loads(payload)
        except AuditionError:
            raise
        except (json.JSONDecodeError, UnicodeError):
            raise _protocol_error("Response is not valid JSON.") from None

        if not isinstance(raw, dict):
            raise _protocol_error("Response must be a JSON object.")
        if raw.get("protocol") != PROTOCOL:
            raise _protocol_error("Response protocol version is invalid.")
        request_id = raw.get("request_id")
        if not isinstance(request_id, str) or request_id != expected_request_id:
            raise _protocol_error("Response request identifier does not match.")

        ok = raw.get("ok")
        if not isinstance(ok, bool):
            raise _protocol_error("Response success flag must be boolean.")
        if ok:
            if set(raw) != {"protocol", "request_id", "ok", "result"}:
                raise _protocol_error("Successful response fields are invalid.")
            result = raw.get("result")
            if not isinstance(result, dict):
                raise _protocol_error("Successful response result must be an object.")
            return cls(request_id=request_id, result=result)

        if set(raw) != {"protocol", "request_id", "ok", "error"}:
            raise _protocol_error("Error response fields are invalid.")
        error = raw.get("error")
        if not isinstance(error, dict) or set(error) != {
            "code",
            "message",
            "retryable",
        }:
            raise _protocol_error("Remote error fields are invalid.")
        code_value = error.get("code")
        message = error.get("message")
        retryable = error.get("retryable")
        if (
            not isinstance(code_value, str)
            or not isinstance(message, str)
            or not message
            or len(message) > 2048
            or not isinstance(retryable, bool)
        ):
            raise _protocol_error("Remote error values are invalid.")
        try:
            code = ErrorCode(code_value)
        except ValueError:
            raise _protocol_error("Remote error code is not recognized.") from None
        raise AuditionError(code, message, retryable=retryable)
