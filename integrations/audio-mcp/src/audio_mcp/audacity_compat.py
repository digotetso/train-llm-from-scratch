from __future__ import annotations

import atexit
import sys
from collections.abc import Callable


def read_framed_response(
    readline: Callable[[], str],
    *,
    wait_ready: Callable[[float], bool],
    timeout: float,
) -> str:
    """Read one Audacity reply, ignoring empty frames before its first line."""
    if timeout <= 0 or not wait_ready(timeout):
        raise TimeoutError(
            "Timed out before receiving a complete Audacity response."
        )

    lines: list[str] = []

    while True:
        # Do not poll the file descriptor between reads. TextIOWrapper may
        # already hold the remaining response even when select() reports that
        # the underlying descriptor is no longer readable.
        line = readline()
        if line == "":
            raise EOFError(
                "Audacity closed the pipe before receiving a complete "
                "Audacity response."
            )
        if line.strip() == "":
            if lines:
                return "".join(lines)
            continue
        lines.append(line)


def _posix_send_raw_compat(self: object, command_str: str) -> str:
    import select

    from audacity_mcp_shared.constants import Timeouts
    from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode

    try:
        self._to_pipe.write(command_str)
        self._to_pipe.flush()
    except OSError as error:
        self._close_pipes()
        raise AudacityMCPError(
            ErrorCode.PIPE_WRITE_FAILED,
            str(error),
        ) from error

    try:
        return read_framed_response(
            self._from_pipe.readline,
            wait_ready=lambda remaining: bool(
                select.select(
                    [self._from_pipe],
                    [],
                    [],
                    remaining,
                )[0]
            ),
            timeout=Timeouts.PIPE_READ,
        )
    except TimeoutError as error:
        self._close_pipes()
        raise AudacityMCPError(
            ErrorCode.PIPE_TIMEOUT,
            (
                f"Pipe read timed out after {Timeouts.PIPE_READ}s — "
                "Audacity may have stopped responding"
            ),
        ) from error
    except (EOFError, OSError) as error:
        self._close_pipes()
        raise AudacityMCPError(
            ErrorCode.PIPE_READ_FAILED,
            str(error),
        ) from error


def configure_shutdown(client: object) -> None:
    atexit.unregister(client.close)
    atexit.register(client._close_pipes)


def main() -> None:
    if sys.platform != "win32":
        from audacity_mcp.audacity_client import AudacityClient

        AudacityClient._posix_send_raw = _posix_send_raw_compat

    from audacity_mcp import main as upstream

    configure_shutdown(upstream.client)
    upstream.main()


if __name__ == "__main__":
    main()
