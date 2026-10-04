"""Muse Protocol provisioning API.

One click -> one tenant -> one AgentMail inbox (+ phone number when telephony lands).
"""
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server import db
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
    username = f"{slugify(req.name)}-{tenant_id[-6:]}"
    try:
        inbox = provision_inbox(
            username=username,
            client_id=tenant_id,
            metadata={"tenant_id": tenant_id, "pack": req.pack, "name": req.name},
        )
    except Exception as e:
        raise HTTPException(502, f"inbox provisioning failed: {e}")

    tenant = {
        "id": tenant_id,
        "name": req.name,
        "email": req.email,
        "pack": req.pack,
        "inbox_id": inbox["inbox_id"],
        "inbox_email": inbox["inbox_email"],
        "phone": None,  # telephony provisioning lands here
        "created_at": db.now(),
    }
    db.save(tenant)
    return {
        "tenant_id": tenant_id,
        "inbox_email": inbox["inbox_email"],
        "pack": req.pack,
        "message": (
            f"You're set up. Your agent's email is {inbox['inbox_email']} — "
            "forward it anything, or email it like an employee. "
            "Texting lands when phone provisioning ships."
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


@app.post("/v1/webhooks/agentmail")
def agentmail_webhook(payload: dict):
    """Receives AgentMail inbound events. The agent loop attaches here next."""
    # TODO: route inbound mail to the tenant's agent run
    return {"received": True, "type": payload.get("type", "unknown")}
