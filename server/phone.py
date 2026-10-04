"""AgentPhone provisioning. One agent persona + phone number per tenant.

Flow per tenant:
  1. POST /v1/agents            -> agent persona (the tenant's agent)
  2. POST /v1/numbers           -> SMS+voice-enabled number
  3. POST /v1/agents/{id}/numbers -> attach number to the agent
  4. POST /v1/agents/{id}/webhook -> per-agent webhook for inbound events
"""
import os

import requests

API_BASE = "https://api.agentphone.ai/v1"


def _headers():
    key = os.environ.get("AGENTPHONE_API_KEY", "")
    if not key:
        raise RuntimeError("AGENTPHONE_API_KEY is not set")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _post(path: str, body: dict) -> dict:
    resp = requests.post(f"{API_BASE}{path}", headers=_headers(), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def provision_phone(name: str, webhook_base: str = "") -> dict:
    """Create the tenant's agent, number, attachment, and webhook. Returns IDs + number."""
    agent = _post("/agents", {"name": name})
    agent_id = agent.get("id") or agent.get("agent_id") or agent.get("agentId")
    if not agent_id:
        raise RuntimeError(f"agent create returned no id: {agent}")

    number = _post("/numbers", {})
    number_id = number.get("id") or number.get("number_id") or number.get("numberId")
    phone = number.get("phone_number") or number.get("phoneNumber") or number.get("number")
    if not number_id:
        raise RuntimeError(f"number provision returned no id: {number}")

    _post(f"/agents/{agent_id}/numbers", {"numberId": number_id})

    if webhook_base:
        _post(
            f"/agents/{agent_id}/webhook",
            {"url": f"{webhook_base.rstrip('/')}/v1/webhooks/agentphone", "timeout": 30},
        )

    return {"agent_id": agent_id, "number_id": number_id, "phone": phone}


def send_message(agent_id: str, to_number: str, body: str, from_number: str = "") -> dict:
    """Send SMS (or iMessage) as the tenant's agent."""
    payload = {"to_number": to_number, "body": body, "agent_id": agent_id}
    if from_number:
        payload["from_number"] = from_number
    return _post("/messages", payload)
