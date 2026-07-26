from collections.abc import Callable

import pytest

from audio_mcp import audacity_compat
from audio_mcp.audacity_compat import read_framed_response


def _reader(lines: list[str]) -> Callable[[], str]:
    values = iter(lines)
    return lambda: next(values)


def test_reader_skips_leading_blank_frames_before_response() -> None:
    waits: list[float] = []

    def wait_once(timeout: float) -> bool:
        waits.append(timeout)
        return True

    result = read_framed_response(
        _reader(
            [
                "\n",
                "\r\n",
                "BatchCommand finished: OK\n",
                "\n",
            ]
        ),
        wait_ready=wait_once,
        timeout=1.0,
    )

    assert result == "BatchCommand finished: OK\n"
    assert waits == [1.0]


def test_reader_preserves_multiline_response_until_blank_terminator() -> None:
    result = read_framed_response(
        _reader(
            [
                "\n",
                "[\n",
                '  { "name": "input", "kind": "wave" }\n',
                "]\n",
                "BatchCommand finished: OK\n",
                "\n",
            ]
        ),
        wait_ready=lambda _: True,
        timeout=1.0,
    )

    assert result == (
        "[\n"
        '  { "name": "input", "kind": "wave" }\n'
        "]\n"
        "BatchCommand finished: OK\n"
    )


def test_reader_times_out_instead_of_accepting_empty_response() -> None:
    with pytest.raises(TimeoutError, match="complete Audacity response"):
        read_framed_response(
            _reader([]),
            wait_ready=lambda _: False,
            timeout=1.0,
        )


def test_reader_rejects_pipe_eof_before_complete_response() -> None:
    with pytest.raises(EOFError, match="complete Audacity response"):
        read_framed_response(
            _reader([""]),
            wait_ready=lambda _: True,
            timeout=1.0,
        )


def test_shutdown_hook_closes_pipes_synchronously(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    class FakeClient:
        async def close(self) -> None:
            return None

        def _close_pipes(self) -> None:
            return None

    client = FakeClient()
    monkeypatch.setattr(
        audacity_compat.atexit,
        "unregister",
        lambda callback: calls.append(("unregister", callback)),
    )
    monkeypatch.setattr(
        audacity_compat.atexit,
        "register",
        lambda callback: calls.append(("register", callback)),
    )

    audacity_compat.configure_shutdown(client)

    assert calls == [
        ("unregister", client.close),
        ("register", client._close_pipes),
    ]
