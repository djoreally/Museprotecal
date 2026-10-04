# Muse Protocol

One click → one tenant → one agent. Pick a pack, get an agent with its own
email address (and soon, its own phone number). Talk to it like an employee.

## How it works

1. Customer picks a pack on the signup page (or the Skill Store links here).
2. `POST /v1/provision` creates a dedicated AgentMail inbox via
   `POST /v0/inboxes` — idempotent per tenant via `client_id`, tagged with
   `metadata.tenant_id`.
3. The tenant row (SQLite) maps the human to their inbox + pack.
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

- ~~Phone/SMS provisioning per tenant (telephony provider)~~ **done** —
  Twilio buys an SMS-capable number per tenant and points it at
  `/v1/webhooks/sms`. Needs `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` in `.env`.
- ~~Agent loop~~ **v1 done** — inbound mail/SMS routes to the tenant's pack
  handler and replies in the same channel. `server/agent.py:run_agent` is the
  plug-in point for a real model (e.g. the Muse model API at dev.meta.ai).
- Skill Store deep link: pack cards link straight to `/?pack=front-desk`.
- Billing: pass AgentMail + Twilio usage through per tenant.
