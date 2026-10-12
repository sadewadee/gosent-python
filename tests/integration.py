#!/usr/bin/env python3
"""Runs against the REAL portal-api started by sdks/tests/integration.sh.

GOSENT_API_KEY and API_BASE come from the environment. The payloads match the
README examples.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gosent  # noqa: E402

api_key = os.environ["GOSENT_API_KEY"]
base_url = os.environ["API_BASE"]
FROM = "hello@sdk-test.gosent.net"

client = gosent.Gosent(api_key=api_key, base_url=base_url)

# 1. send() (contract §4.1)
result = client.emails.send(
    from_=FROM,
    to="you@example.com",
    subject="Hello from Gosent",
    html="<p>Your first email is on its way.</p>",
)
assert result.succeeded == 1, "expected 1 accepted, got {0!r}".format(result)
assert result.email_id, "email_id is empty"
print("  python send(): 200 succeeded={0} email_id={1}".format(result.succeeded, result.email_id))

# 2. send_mime() (contract §4.2)
mime = "\r\n".join(
    [
        "From: {0}".format(FROM),
        "To: you@example.com",
        "Subject: Hello from Gosent",
        "",
        "Your first email is on its way.",
    ]
)
result = client.emails.send_mime(mime)
assert result.succeeded == 1, "expected 1 accepted, got {0!r}".format(result)
print("  python send_mime(): 200 succeeded={0} email_id={1}".format(result.succeeded, result.email_id))

# 3. an unverified sender is refused with the documented 400 + code
try:
    client.emails.send(from_="hello@not-verified.gosent.net", to="you@example.com", subject="nope", text="nope")
    raise AssertionError("an unverified sender must not succeed")
except gosent.GosentError as err:
    assert err.status_code == 400, "expected 400, got {0!r}".format(err)
    assert err.code == "SENDER_NOT_VERIFIED", "expected SENDER_NOT_VERIFIED, got {0!r}".format(err)
    print("  python unverified: {0} {1}".format(err.status_code, err.code))
