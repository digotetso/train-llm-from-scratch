import json

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.protocol import MAX_MESSAGE_BYTES, PROTOCOL, Request, Response


def test_request_has_version_id_operation_arguments_and_deadline() -> None:
    request = Request.create("get_status", {}, timeout_ms=5000)

    payload = json.loads(request.to_json())

    assert payload == {
        "protocol": PROTOCOL,
        "request_id": request.request_id,
        "operation": "get_status",
        "arguments": {},
        "deadline_ms": 5000,
    }
    assert len(request.request_id) == 32


@pytest.mark.parametrize(
    ("operation", "arguments", "timeout_ms"),
    [
        ("", {}, 5000),
        ("get-status", {}, 5000),
        ("get_status", [], 5000),
        ("get_status", {}, True),
        ("get_status", {}, 0),
        ("get_status", {}, 60_001),
    ],
)
def test_request_rejects_malformed_fields(
    operation: object, arguments: object, timeout_ms: object
) -> None:
    with pytest.raises(AuditionError) as caught:
        Request.create(operation, arguments, timeout_ms=timeout_ms)  # type: ignore[arg-type]

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_request_rejects_oversized_utf8_payload() -> None:
    request = Request.create(
        "open",
        {"path": "é" * MAX_MESSAGE_BYTES},
        timeout_ms=5000,
    )

    with pytest.raises(AuditionError) as caught:
        request.to_json()

    assert caught.value.code is ErrorCode.PROTOCOL_ERROR


def test_response_accepts_correlated_success_object() -> None:
    payload = json.dumps(
        {
            "protocol": PROTOCOL,
            "request_id": "expected",
            "ok": True,
            "result": {"application": "Audition"},
        }
    )

    response = Response.from_json(payload, expected_request_id="expected")

    assert response.result == {"application": "Audition"}


def test_response_rejects_wrong_request_id() -> None:
    payload = json.dumps(
        {
            "protocol": PROTOCOL,
            "request_id": "wrong",
            "ok": True,
            "result": {},
        }
    )

    with pytest.raises(AuditionError) as caught:
        Response.from_json(payload, expected_request_id="expected")

    assert caught.value.code is ErrorCode.PROTOCOL_ERROR


def test_response_rejects_oversized_payload() -> None:
    with pytest.raises(AuditionError) as caught:
        Response.from_json(
            "x" * (MAX_MESSAGE_BYTES + 1),
            expected_request_id="id",
        )

    assert caught.value.code is ErrorCode.PROTOCOL_ERROR


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        json.dumps(
            {
                "protocol": "wrong",
                "request_id": "id",
                "ok": True,
                "result": {},
            }
        ),
        json.dumps(
            {
                "protocol": PROTOCOL,
                "request_id": "id",
                "ok": 1,
                "result": {},
            }
        ),
        json.dumps(
            {
                "protocol": PROTOCOL,
                "request_id": "id",
                "ok": True,
                "result": [],
            }
        ),
        json.dumps(
            {
                "protocol": PROTOCOL,
                "request_id": "id",
                "ok": True,
                "result": {},
                "unexpected": "field",
            }
        ),
    ],
)
def test_response_rejects_malformed_envelopes(payload: str) -> None:
    with pytest.raises(AuditionError) as caught:
        Response.from_json(payload, expected_request_id="id")

    assert caught.value.code is ErrorCode.PROTOCOL_ERROR


def test_response_maps_allowlisted_remote_error() -> None:
    payload = json.dumps(
        {
            "protocol": PROTOCOL,
            "request_id": "id",
            "ok": False,
            "error": {
                "code": "DOCUMENT_NOT_OPEN",
                "message": "Open a document first.",
                "retryable": False,
            },
        }
    )

    with pytest.raises(AuditionError) as caught:
        Response.from_json(payload, expected_request_id="id")

    assert caught.value.code is ErrorCode.DOCUMENT_NOT_OPEN
    assert str(caught.value) == "Open a document first."
    assert caught.value.retryable is False


def test_response_converts_unknown_remote_error_to_protocol_error() -> None:
    payload = json.dumps(
        {
            "protocol": PROTOCOL,
            "request_id": "id",
            "ok": False,
            "error": {
                "code": "INVENTED_CODE",
                "message": "No",
                "retryable": False,
            },
        }
    )

    with pytest.raises(AuditionError) as caught:
        Response.from_json(payload, expected_request_id="id")

    assert caught.value.code is ErrorCode.PROTOCOL_ERROR
    assert "INVENTED_CODE" not in str(caught.value)
