# Muse Protocol

One click → one tenant → one agent. Pick a pack, get an agent with its own
email address (and soon, its own phone number). Talk to it like an employee.

## How it works

1. Customer picks a pack on the signup page (or the Skill Store links here).
2. `POST /v1/provision` creates a dedicated AgentMail inbox via
   `POST /v0/inboxes` — idempotent per tenant via `client_id`, tagged with
   `metadata.tenant_id`.
3. The tenant row (database) maps the human to their inbox + pack.
4. Inbound mail hits `POST /v1/webhooks/agentmail` — the agent loop attaches here.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env        # add your AGENTMAIL_API_KEY
uvicorn server.main:app --port 8000
```

Open http://localhost:8000, pick a pack, enter a name + email.

## API

- `GET /v1/packs` — available packs
- `POST /v1/provision` `{name, email, pack}` — provision a tenant + inbox
- `GET /v1/tenants` — list tenants
- `GET /v1/tenants/{id}` — one tenant
- `POST /v1/webhooks/agentmail` — inbound mail events

## Roadmap

- ~~Phone provisioning per tenant~~ **done** — AgentPhone creates the
  tenant's agent persona, provisions an SMS+voice number, attaches it, and
  points the per-agent webhook at `/v1/webhooks/agentphone`. Needs
  `AGENTPHONE_API_KEY` in `.env`. Customers can call *and* text their agent.
- ~~Agent loop~~ **v1 done** — inbound mail/SMS/voice routes to the tenant's
  pack handler and replies in the same channel (voice turns return
  `{"text": ...}` live). `server/agent.py:run_agent` calls Meta's Muse Wonder via the Responses API; it requires a server-side `MODEL_API_KEY`.
- Skill Store deep link: pack cards link straight to `/?pack=front-desk`.
- Billing: pass AgentMail + AgentPhone usage through per tenant.

## Meta Muse Wonder setup

Set `MODEL_API_KEY` on the server to a current Meta Model API key. The default model is `muse-wonder-1.0` at `https://api.meta.ai/v1/responses`. Optional overrides: `META_MODEL`, `META_API_BASE_URL`, and `META_REASONING_EFFORT`. Do not set the key in frontend code or commit it.

The incoming email/SMS/voice webhooks now call Muse rather than an acknowledgement stub. API failures return HTTP 502 and do **not** send a fake success reply. Deploy the code and environment configuration on your VPS separately.

Test the integration without Meta network access using `python -m unittest discover -s tests -v`. A live API smoke test and phone/email delivery tests must be run after provisioning the new key on the VPS.
