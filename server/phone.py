"""Twilio phone provisioning. One SMS-capable number per tenant."""
import os


def _client():
    from twilio.rest import Client

    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set")
    return Client(sid, token)


def provision_phone_number(area_code: str = "", webhook_base: str = "") -> dict:
    """Buy an SMS-capable US number and point its SMS webhook at us."""
    client = _client()
    search = {"sms_enabled": True, "limit": 1}
    if area_code:
        search["area_code"] = area_code
    available = client.available_phone_numbers("US").local.list(**search)
    if not available:
        raise RuntimeError("no SMS-capable numbers available")
    kwargs = {"phone_number": available[0].phone_number}
    if webhook_base:
        kwargs["sms_url"] = f"{webhook_base.rstrip('/')}/v1/webhooks/sms"
        kwargs["sms_method"] = "POST"
    number = client.incoming_phone_numbers.create(**kwargs)
    return {"phone": number.phone_number, "sid": number.sid}


def send_sms(from_number: str, to: str, body: str) -> dict:
    client = _client()
    msg = client.messages.create(from_=from_number, to=to, body=body)
    return {"sid": msg.sid}
