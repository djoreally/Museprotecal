"""Muse Protocol provisioning API.

One click -> one tenant -> one AgentMail inbox + one phone number.
Inbound mail/SMS -> agent loop -> reply, scoped per tenant.
"""
import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from server import db
from server.agent import handle_inbound
from server.comms import send_email
from server.provision import provision_inbox, slugify

load_dotenv()
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

    # 2. Phone number (best effort — skipped if Twilio isn't configured)
    phone = None
    phone_note = "Texting activates once phone provisioning is configured."
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        from server.phone import provision_phone_number

        try:
            result = provision_phone_number(
                area_code=req.area_code,
                webhook_base=os.environ.get("WEBHOOK_BASE", ""),
            )
            phone = result["phone"]
            phone_note = f"Text {phone} like an employee — your agent answers."
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


def _find_tenant_by_phone(phone: str):
    for t in db.list_all():
        if t.get("phone") == phone:
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


@app.post("/v1/webhooks/sms")
async def sms_webhook(request: Request):
    """Inbound SMS (Twilio) -> tenant's agent -> SMS reply."""
    form = await request.form()
    to_number = form.get("To", "")
    from_number = form.get("From", "")
    body = form.get("Body", "")
    tenant = _find_tenant_by_phone(to_number)
    if not tenant:
        return PlainTextResponse("<Response></Response>", media_type="text/xml")
    reply = handle_inbound(tenant, "sms", from_number, body)
    try:
        from server.phone import send_sms

        send_sms(tenant["phone"], from_number, reply)
    except Exception:
        pass
    return PlainTextResponse("<Response></Response>", media_type="text/xml")
