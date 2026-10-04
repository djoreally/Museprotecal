"""The agent loop (v1).

Inbound message -> handle_inbound -> reply.

This is intentionally a small, honest stub: it acknowledges and logs so the
full loop (webhook in, reply out, scoped per tenant) is proven end to end.
Plug a real model in `run_agent` — e.g. the Muse model API at dev.meta.ai —
and every tenant gets a thinking agent with zero changes to the webhooks.
"""


def run_agent(tenant: dict, channel: str, sender: str, body: str) -> str:
    """Return the reply text for an inbound message. Replace with an LLM call."""
    pack = tenant.get("pack", "general")
    name = tenant.get("name", "there")
    return (
        f"Hi {name} — got your {channel} message: \"{body[:160]}\". "
        f"I'm running your {pack} pack. A full reply is coming right up."
    )


def handle_inbound(tenant: dict, channel: str, sender: str, body: str) -> str:
    # Future: load tenant memory, pack workflow, and conversation history here,
    # then call run_agent with all of it.
    return run_agent(tenant, channel, sender, body)
