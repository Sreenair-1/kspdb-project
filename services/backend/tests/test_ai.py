from unittest.mock import MagicMock, patch

from app.ai import generate_fault_summary
from app.domain.models import LocalizedFault


def _make_fault(incident_type: str = "span") -> LocalizedFault:
    return LocalizedFault(
        incident_type=incident_type,
        feeder_id="F-07-03",
        dt_id="D-0112",
        upstream_pole_id="P-000001",
        downstream_pole_id="P-000002",
        latitude=12.9682,
        longitude=77.5946,
        pincode="560078",
        affected_poles=5,
        confidence=0.92,
        confidence_reasons=["live_dark_boundary", "high_coverage"],
    )


# ---------------------------------------------------------------------------
# Graceful degradation — no API key
# ---------------------------------------------------------------------------


def test_returns_none_when_api_key_is_empty() -> None:
    result = generate_fault_summary(_make_fault(), api_key="")
    assert result is None


def test_returns_none_when_api_key_is_whitespace() -> None:
    result = generate_fault_summary(_make_fault(), api_key="   ")
    # whitespace is treated as present (non-empty string) — still tries the call;
    # the API will reject it with 401 which is caught and returns None
    # This verifies the exception-catch path
    with patch("app.ai.httpx.post", side_effect=Exception("connection refused")):
        result = generate_fault_summary(_make_fault(), api_key="   ")
    assert result is None


# ---------------------------------------------------------------------------
# Happy path — successful API response
# ---------------------------------------------------------------------------


def test_returns_summary_text_on_successful_api_response() -> None:
    expected = (
        "Span fault on feeder F-07-03 between poles P-000001→P-000002; "
        "5 poles dark at 12.9682°N, 77.5946°E, PIN 560078."
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": expected}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.ai.httpx.post", return_value=mock_response):
        result = generate_fault_summary(_make_fault(), api_key="gsk-test-key")

    assert result == expected


def test_sends_correct_headers_and_model() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Fault summary."}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.ai.httpx.post", return_value=mock_response) as mock_post:
        generate_fault_summary(_make_fault(), api_key="gsk-groq-key")

    call_kwargs = mock_post.call_args
    headers = call_kwargs.kwargs["headers"]
    payload = call_kwargs.kwargs["json"]

    assert headers["Authorization"] == "Bearer gsk-groq-key"
    assert payload["model"] == "llama-3.1-8b-instant"
    assert payload["max_tokens"] == 120


# ---------------------------------------------------------------------------
# Degradation — network / API errors
# ---------------------------------------------------------------------------


def test_returns_none_on_httpx_timeout() -> None:
    import httpx

    with patch("app.ai.httpx.post", side_effect=httpx.TimeoutException("timed out")):
        result = generate_fault_summary(_make_fault(), api_key="sk-test-key")

    assert result is None


def test_returns_none_on_http_error_status() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

    with patch("app.ai.httpx.post", return_value=mock_response):
        result = generate_fault_summary(_make_fault(), api_key="sk-bad-key")

    assert result is None


def test_returns_none_when_choices_array_empty() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": []}
    mock_response.raise_for_status.return_value = None

    with patch("app.ai.httpx.post", return_value=mock_response):
        result = generate_fault_summary(_make_fault(), api_key="gsk-test-key")

    assert result is None


def test_fault_description_includes_key_fields() -> None:
    """The prompt sent to the LLM must include location and affected pole count."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.ai.httpx.post", return_value=mock_response) as mock_post:
        generate_fault_summary(_make_fault(), api_key="gsk-test-key")

    payload = mock_post.call_args.kwargs["json"]
    user_content = payload["messages"][1]["content"]

    assert "560078" in user_content
    assert "12.9682" in user_content
    assert "F-07-03" in user_content
    assert "5" in user_content
