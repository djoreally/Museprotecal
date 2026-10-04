"""Outbound comms: email via AgentMail, SMS via Twilio."""
import os

import requests

from server.provision import API_BASE, _headers


def send_email(inbox_id: str, to: str, subject: str, text: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/v0/inboxes/{inbox_id}/messages/send",
        headers=_headers(),
        json={"to": [to], "subject": subject, "text": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
