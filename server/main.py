"""Muse Protocol provisioning API.

One click -> one tenant -> one AgentMail inbox + one phone number.
Inbound mail/SMS -> agent loop -> reply, scoped per tenant.
"""
import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server import db
from server.agent import handle_inbound
from server.comms import send_email
from server.provision import provision_inbox, slugify

load_dotenv()
load_dotenv(".env.local", override=False)
db.init()

app = FastAPI(title="Muse Protocol")
PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def load_packs():
    packs = []
    for f in sorted(PACKS_DIR.glob("*.json")):
        packs.append(json.loads(f.read_text()))
    return packs


class ProvisionRequest(BaseModel):
    name: str
    email: str
    pack: str
    area_code: str = ""


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/v1/packs")
def packs():
    return {"packs": load_packs()}


@app.post("/v1/provision")
def provision(req: ProvisionRequest):
    pack_ids = [p["id"] for p in load_packs()]
    if req.pack not in pack_ids:
        raise HTTPException(400, f"unknown pack '{req.pack}'. choose from: {pack_ids}")

    tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"

    # 1. Email inbox (required)
    username = f"{slugify(req.name)}-{tenant_id[-6:]}"
    try:
        inbox = provision_inbox(
            username=username,
            client_id=tenant_id,
            metadata={"tenant_id": tenant_id, "pack": req.pack, "name": req.name},
        )
    except Exception as e:
        raise HTTPException(502, f"inbox provisioning failed: {e}")

    # 2. Phone number via AgentPhone (best effort — skipped if not configured)
    phone = None
    agentphone_agent_id = None
    phone_note = "Texting activates once phone provisioning is configured."
    if os.environ.get("AGENTPHONE_API_KEY"):
        from server.phone import provision_phone

        try:
            result = provision_phone(
                name=f"{req.name} agent",
                webhook_base=os.environ.get("WEBHOOK_BASE", ""),
            )
            phone = result["phone"]
            agentphone_agent_id = result["agent_id"]
            phone_note = (
                f"Call or text {phone} like an employee — your agent answers."
            )
        except Exception as e:
            phone_note = f"Phone provisioning failed (inbox is live): {e}"

    tenant = {
        "id": tenant_id,
        "name": req.name,
        "email": req.email,
        "pack": req.pack,
        "inbox_id": inbox["inbox_id"],
        "inbox_email": inbox["inbox_email"],
        "phone": phone,
        "agentphone_agent_id": agentphone_agent_id,
        "created_at": db.now(),
    }
    db.save(tenant)
    return {
        "tenant_id": tenant_id,
        "inbox_email": inbox["inbox_email"],
        "phone": phone,
        "pack": req.pack,
        "message": (
            f"You're set up. Email your agent at {inbox['inbox_email']}. "
            + phone_note
        ),
    }


@app.get("/v1/tenants")
def tenants():
    return {"tenants": db.list_all()}


@app.get("/v1/tenants/{tenant_id}")
def tenant(tenant_id: str):
    t = db.get(tenant_id)
    if not t:
        raise HTTPException(404, "unknown tenant")
    return t


def _find_tenant_by_inbox(inbox_id: str):
    for t in db.list_all():
        if t.get("inbox_id") == inbox_id:
            return t
    return None


def _find_tenant_by_agentphone(agent_id: str):
    for t in db.list_all():
        if t.get("agentphone_agent_id") == agent_id:
            return t
    return None


@app.post("/v1/webhooks/agentmail")
def agentmail_webhook(payload: dict):
    """Inbound mail -> tenant's agent -> email reply."""
    inbox_id = payload.get("inbox_id") or payload.get("inboxId", "")
    tenant = _find_tenant_by_inbox(inbox_id) if inbox_id else None
    if not tenant:
        return {"received": True, "handled": False, "reason": "unknown inbox"}
    sender = payload.get("from") or payload.get("sender", "")
    body = payload.get("text") or payload.get("body") or payload.get("preview", "")
    subject = payload.get("subject", "")
    reply = handle_inbound(tenant, "email", sender, f"{subject}\n{body}".strip())
    try:
        send_email(tenant["inbox_id"], sender, f"Re: {subject}", reply)
        return {"received": True, "handled": True}
    except Exception as e:
        return {"received": True, "handled": False, "reason": str(e)}


@app.post("/v1/webhooks/agentphone")
def agentphone_webhook(payload: dict):
    """Inbound SMS/voice via AgentPhone -> tenant's agent -> reply.

    Voice channel: AgentPhone expects {"text": ...} back for the live turn.
    SMS channel: 200 OK is enough; the reply goes out via POST /v1/messages.
    """
    if payload.get("event") not in ("agent.message", "message.received"):
        # call_ended transcripts etc: acknowledge, handle later
        return {"received": True, "handled": False, "reason": "event ignored"}

    agent_id = payload.get("agentId") or payload.get("agent_id", "")
    tenant = _find_tenant_by_agentphone(agent_id) if agent_id else None
    if not tenant:
        return {"received": True, "handled": False, "reason": "unknown agent"}

    data = payload.get("data", {}) or {}
    sender = data.get("from", "")
    body = data.get("message") or data.get("body") or data.get("transcript", "")
    channel = payload.get("channel", "sms")

    reply = handle_inbound(tenant, channel, sender, body)

    if channel == "voice":
        return {"text": reply}

    try:
        from server.phone import send_message

        send_message(
            agent_id=tenant["agentphone_agent_id"],
            to_number=sender,
            body=reply,
            from_number=tenant.get("phone") or "",
        )
        return {"received": True, "handled": True}
    except Exception as e:
        return {"received": True, "handled": False, "reason": str(e)}

