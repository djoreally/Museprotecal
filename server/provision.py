"""AgentMail inbox provisioning. One inbox per tenant, idempotent via client_id."""
import os
import re

import requests

API_BASE = "https://api.agentmail.to"


def _headers():
    key = os.environ.get("AGENTMAIL_API_KEY", "")
    if not key:
        raise RuntimeError("AGENTMAIL_API_KEY is not set")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agent"


def provision_inbox(username: str, client_id: str, metadata: dict) -> dict:
    """POST /v0/inboxes. Same client_id returns the original inbox (no duplicates)."""
    resp = requests.post(
        f"{API_BASE}/v0/inboxes",
        headers=_headers(),
        json={
            "username": username,
            "client_id": client_id,
            "metadata": metadata,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "inbox_id": data.get("inbox_id") or data.get("id"),
        "inbox_email": data.get("email") or data.get("inbox_email"),
        "raw": data,
    }
