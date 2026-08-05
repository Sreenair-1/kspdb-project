from __future__ import annotations

import httpx

from app.domain.models import LocalizedFault


def generate_fault_summary(fault: LocalizedFault, api_key: str) -> str | None:
    """Generate a plain-English fault summary via the Groq chat-completions API.

    Returns None when api_key is blank, the call times out, or any error occurs,
    so ticket creation is never blocked by AI unavailability.

    Provider-agnostic design: swap the endpoint URL and model string to use a
    different HTTP-based LLM without changing any other code.
    """
    if not api_key:
        return None

    parts: list[str] = [f"Fault type: {fault.incident_type}"]
    if fault.feeder_id:
        parts.append(f"Feeder: {fault.feeder_id}")
    if fault.dt_id:
        parts.append(f"Distribution transformer: {fault.dt_id}")
    if fault.upstream_pole_id and fault.downstream_pole_id:
        parts.append(f"Span: poles {fault.upstream_pole_id} → {fault.downstream_pole_id}")
    if fault.latitude and fault.longitude:
        parts.append(f"Coordinates: {fault.latitude:.4f}°N, {fault.longitude:.4f}°E")
    if fault.pincode:
        parts.append(f"PIN code: {fault.pincode}")
    parts.append(f"Affected poles: {fault.affected_poles}")
    parts.append(f"Confidence: {round(fault.confidence * 100)}%")
    if fault.confidence_reasons:
        parts.append(f"Evidence: {', '.join(fault.confidence_reasons)}")

    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "max_tokens": 120,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant for a power distribution board control room. "
                            "Write one concise sentence (max 40 words) for a field operator. "
                            "State: what failed, where, how many poles are affected, "
                            "and the navigation coordinates. "
                            "No preamble — just the actionable facts."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this power fault:\n\n{chr(10).join(parts)}",
                    },
                ],
            },
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content")
            if content:
                return content.strip()
        return None
    except Exception:  # noqa: BLE001
        return None
