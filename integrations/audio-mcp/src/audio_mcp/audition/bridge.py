from __future__ import annotations

import asyncio
import hmac
import json
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from audio_mcp.audition.config import AuditionConfig
from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.protocol import MAX_MESSAGE_BYTES, Request, Response


AUTH_TIMEOUT_SECONDS = 2
MAX_PENDING_REQUESTS = 8


class AuditionBridge:
    def __init__(self, config: AuditionConfig) -> None:
        if config.host != "127.0.0.1":
            raise ValueError("Audition bridge host must be exactly 127.0.0.1.")
        self._config = config
        self._server: Server | None = None
        self._connection: ServerConnection | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    @property
    def connected(self) -> bool:
        return self._connection is not None

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await serve(
            self._handle_connection,
            self._config.host,
            self._config.port,
            compression=None,
            max_size=MAX_MESSAGE_BYTES,
            max_queue=8,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            origins=None,
        )

    async def close(self) -> None:
        connection = self._connection
        self._connection = None
        self._fail_pending(
            AuditionError(
                ErrorCode.BRIDGE_UNAVAILABLE,
                "Audition bridge is shutting down.",
                retryable=True,
            )
        )
        if connection is not None:
            await connection.close(code=1001, reason="Bridge shutdown")

        server = self._server
        self._server = None
        if server is not None:
            server.close(
                close_connections=True,
                code=1001,
                reason="Bridge shutdown",
            )
            await server.wait_closed()

    async def request(
        self,
        operation: str,
        arguments: dict[str, Any],
        timeout_ms: int = 5000,
    ) -> dict[str, Any]:
        connection = self._connection
        if connection is None:
            raise AuditionError(
                ErrorCode.BRIDGE_UNAVAILABLE,
                "Adobe Audition CEP bridge is not connected.",
                retryable=True,
            )
        if len(self._pending) >= MAX_PENDING_REQUESTS:
            raise AuditionError(
                ErrorCode.BRIDGE_UNAVAILABLE,
                "Adobe Audition CEP bridge is busy; retry after a request completes.",
                retryable=True,
            )

        request = Request.create(operation, arguments, timeout_ms)
        payload = request.to_json()
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[request.request_id] = future
        try:
            try:
                await connection.send(payload)
            except ConnectionClosed:
                self._consume_future_exception(future)
                raise AuditionError(
                    ErrorCode.BRIDGE_UNAVAILABLE,
                    "Adobe Audition CEP bridge disconnected.",
                    retryable=True,
                ) from None

            try:
                return await asyncio.wait_for(
                    asyncio.shield(future),
                    timeout=timeout_ms / 1000,
                )
            except TimeoutError:
                future.cancel()
                raise AuditionError(
                    ErrorCode.BRIDGE_TIMEOUT,
                    "Adobe Audition CEP bridge did not respond before the deadline.",
                    retryable=False,
                ) from None
            except asyncio.CancelledError:
                future.cancel()
                raise
        finally:
            self._pending.pop(request.request_id, None)

    async def _handle_connection(self, connection: ServerConnection) -> None:
        try:
            try:
                first_message = await asyncio.wait_for(
                    connection.recv(),
                    timeout=AUTH_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                await connection.close(code=1008, reason="Authentication required")
                return
            except ConnectionClosed:
                return

            if not self._valid_authentication(first_message):
                await connection.close(code=1008, reason="Authentication failed")
                return
            if self._connection is not None:
                await connection.close(code=1013, reason="Bridge already connected")
                return

            self._connection = connection
            await connection.send(json.dumps({"type": "authenticated"}))
            async for message in connection:
                if not isinstance(message, str):
                    await connection.close(
                        code=1003,
                        reason="Text protocol frames required",
                    )
                    break
                should_continue = self._route_response(message)
                if not should_continue:
                    await connection.close(
                        code=1002,
                        reason="Malformed protocol frame",
                    )
                    break
        except ConnectionClosed:
            pass
        finally:
            if self._connection is connection:
                self._connection = None
                self._fail_pending(
                    AuditionError(
                        ErrorCode.BRIDGE_UNAVAILABLE,
                        "Adobe Audition CEP bridge disconnected.",
                        retryable=True,
                    )
                )

    def _valid_authentication(self, payload: str | bytes) -> bool:
        if not isinstance(payload, str):
            return False
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return False
        if not isinstance(raw, dict) or set(raw) != {"type", "secret"}:
            return False
        message_type = raw.get("type")
        secret = raw.get("secret")
        return (
            message_type == "authenticate"
            and isinstance(secret, str)
            and hmac.compare_digest(secret, self._config.secret)
        )

    def _route_response(self, payload: str) -> bool:
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return False
        if not isinstance(raw, dict):
            return False
        request_id = raw.get("request_id")
        if not isinstance(request_id, str):
            return False

        future = self._pending.get(request_id)
        if future is None or future.done():
            return True
        try:
            response = Response.from_json(
                payload,
                expected_request_id=request_id,
            )
        except AuditionError as error:
            future.set_exception(self._redacted(error))
        else:
            future.set_result(response.result)
        return True

    def _redacted(self, error: AuditionError) -> AuditionError:
        message = str(error).replace(self._config.secret, "[REDACTED]")
        return AuditionError(
            error.code,
            message,
            retryable=error.retryable,
        )

    def _fail_pending(self, error: AuditionError) -> None:
        pending = tuple(self._pending.values())
        self._pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(error)

    @staticmethod
    def _consume_future_exception(
        future: asyncio.Future[dict[str, Any]],
    ) -> None:
        if future.done() and not future.cancelled():
            future.exception()
