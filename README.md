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

- Phone/SMS provisioning per tenant (telephony provider) — the `phone`
  column and signup copy are already stubbed for it.
- Agent loop: inbound mail/SMS → agent run → reply, scoped per tenant.
- Skill Store deep link: pack cards link straight to `/?pack=front-desk`.
- Billing: pass AgentMail usage through per tenant.
