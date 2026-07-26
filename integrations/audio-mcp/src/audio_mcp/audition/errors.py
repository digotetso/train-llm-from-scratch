from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNAUTHORIZED = "UNAUTHORIZED"
    BRIDGE_UNAVAILABLE = "BRIDGE_UNAVAILABLE"
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    APPLICATION_UNAVAILABLE = "APPLICATION_UNAVAILABLE"
    DOCUMENT_NOT_OPEN = "DOCUMENT_NOT_OPEN"
    PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    APPLICATION_ERROR = "APPLICATION_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class AuditionError(RuntimeError):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
