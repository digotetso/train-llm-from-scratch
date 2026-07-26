import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from audio_mcp.audition.bridge import AuditionBridge, MAX_PENDING_REQUESTS
from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.protocol import MAX_MESSAGE_BYTES, PROTOCOL


async def _authenticate(socket: object, secret: str) -> None:
    await socket.send(  # type: ignore[attr-defined]
        json.dumps({"type": "authenticate", "secret": secret})
    )
    response = json.loads(await socket.recv())  # type: ignore[attr-defined]
    assert response == {"type": "authenticated"}


def test_bridge_authenticates_and_correlates_response(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await _authenticate(socket, config.secret)
                assert bridge.connected

                request_task = asyncio.create_task(
                    bridge.request("get_status", {})
                )
                request = json.loads(await socket.recv())
                assert request["operation"] == "get_status"
                await socket.send(
                    json.dumps(
                        {
                            "protocol": request["protocol"],
                            "request_id": request["request_id"],
                            "ok": True,
                            "result": {"application": "Audition"},
                        }
                    )
                )

                assert await request_task == {"application": "Audition"}
        finally:
            await bridge.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "auth",
    [
        {"type": "authenticate", "secret": "wrong"},
        {"type": "authenticate"},
        {"type": "authenticate", "secret": "a" * 64, "extra": True},
        {"type": "response", "secret": "a" * 64},
        [],
    ],
)
def test_bridge_rejects_unauthorized_first_message(config, auth: object) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await socket.send(json.dumps(auth))
                await socket.wait_closed()
                assert socket.close_code == 1008
                assert not bridge.connected
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_rejects_second_client_without_replacing_first(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(
                f"ws://127.0.0.1:{config.port}"
            ) as first, connect(f"ws://127.0.0.1:{config.port}") as second:
                await _authenticate(first, config.secret)
                await second.send(
                    json.dumps(
                        {"type": "authenticate", "secret": config.secret}
                    )
                )
                await second.wait_closed()
                assert second.close_code == 1013
                assert bridge.connected

                request_task = asyncio.create_task(bridge.request("stop", {}))
                request = json.loads(await first.recv())
                await first.send(
                    json.dumps(
                        {
                            "protocol": PROTOCOL,
                            "request_id": request["request_id"],
                            "ok": True,
                            "result": {"stopped": True},
                        }
                    )
                )
                assert await request_task == {"stopped": True}
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_rejects_request_while_disconnected(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            with pytest.raises(AuditionError) as caught:
                await bridge.request("get_status", {})
            assert caught.value.code is ErrorCode.BRIDGE_UNAVAILABLE
            assert caught.value.retryable is True
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_timeout_removes_pending_and_discards_late_response(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await _authenticate(socket, config.secret)

                timed_out = asyncio.create_task(
                    bridge.request("get_status", {}, timeout_ms=20)
                )
                first_request = json.loads(await socket.recv())
                with pytest.raises(AuditionError) as caught:
                    await timed_out
                assert caught.value.code is ErrorCode.BRIDGE_TIMEOUT
                assert bridge.pending_count == 0

                await socket.send(
                    json.dumps(
                        {
                            "protocol": PROTOCOL,
                            "request_id": first_request["request_id"],
                            "ok": True,
                            "result": {"late": True},
                        }
                    )
                )

                current = asyncio.create_task(
                    bridge.request("get_status", {}, timeout_ms=500)
                )
                second_request = json.loads(await socket.recv())
                await socket.send(
                    json.dumps(
                        {
                            "protocol": PROTOCOL,
                            "request_id": second_request["request_id"],
                            "ok": True,
                            "result": {"late": False},
                        }
                    )
                )
                assert await current == {"late": False}
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_bounds_concurrent_pending_requests(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        tasks: list[asyncio.Task[dict[str, object]]] = []
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await _authenticate(socket, config.secret)
                for _ in range(MAX_PENDING_REQUESTS):
                    task = asyncio.create_task(bridge.request("get_status", {}))
                    tasks.append(task)
                    await socket.recv()

                with pytest.raises(AuditionError) as caught:
                    await bridge.request(
                        "get_status",
                        {},
                        timeout_ms=10,
                    )
                assert caught.value.code is ErrorCode.BRIDGE_UNAVAILABLE
                assert caught.value.retryable is True
                assert bridge.pending_count == MAX_PENDING_REQUESTS
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await bridge.close()

    asyncio.run(scenario())


def test_disconnect_fails_pending_request(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            socket = await connect(f"ws://127.0.0.1:{config.port}")
            await _authenticate(socket, config.secret)
            request_task = asyncio.create_task(bridge.request("get_status", {}))
            await socket.recv()
            await socket.close()

            with pytest.raises(AuditionError) as caught:
                await request_task
            assert caught.value.code is ErrorCode.BRIDGE_UNAVAILABLE
            assert bridge.pending_count == 0
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_rejects_oversized_first_frame(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await socket.send("x" * (MAX_MESSAGE_BYTES + 1))
                await socket.wait_closed()
                assert socket.close_code == 1009
                assert not bridge.connected
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_rejects_oversized_authenticated_response(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await _authenticate(socket, config.secret)
                request_task = asyncio.create_task(
                    bridge.request("get_status", {})
                )
                await socket.recv()
                await socket.send("x" * (MAX_MESSAGE_BYTES + 1))
                await socket.wait_closed()
                assert socket.close_code == 1009

                with pytest.raises(AuditionError) as caught:
                    await request_task
                assert caught.value.code is ErrorCode.BRIDGE_UNAVAILABLE
                assert bridge.pending_count == 0
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_redacts_secret_from_remote_error(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await _authenticate(socket, config.secret)
                request_task = asyncio.create_task(
                    bridge.request("get_status", {})
                )
                request = json.loads(await socket.recv())
                await socket.send(
                    json.dumps(
                        {
                            "protocol": PROTOCOL,
                            "request_id": request["request_id"],
                            "ok": False,
                            "error": {
                                "code": "APPLICATION_ERROR",
                                "message": f"failure {config.secret}",
                                "retryable": False,
                            },
                        }
                    )
                )

                with pytest.raises(AuditionError) as caught:
                    await request_task
                assert config.secret not in str(caught.value)
                assert config.secret not in repr(caught.value)
                assert "[REDACTED]" in str(caught.value)
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_close_is_idempotent(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        await bridge.close()
        await bridge.close()
        assert not bridge.connected
        assert bridge.pending_count == 0

    asyncio.run(scenario())
