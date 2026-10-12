# gosent

Official Python SDK for the Gosent Send API. Send email with a few lines of code.

Requires Python 3.9 or newer. Standard library only: no dependencies to install.

## Install

This package is not published to PyPI yet. Install the wheel built from the repository:

```sh
cd sdks/python
python -m build --wheel
pip install dist/gosent-0.1.0-py3-none-any.whl
```

Or install straight from the source tree:

```sh
pip install /path/to/gosent-portal/sdks/python
```

## Send your first email

```python
import os
import gosent

client = gosent.Gosent(api_key=os.environ["GOSENT_API_KEY"])

result = client.emails.send(
    from_="hello@yourdomain.com",
    to="you@example.com",
    subject="Hello from Gosent",
    html="<p>Your first email is on its way.</p>",
)

print("sent", result.email_id, result.succeeded)
```

The API key defaults to the `GOSENT_API_KEY` environment variable when you omit it:

```python
client = gosent.Gosent()
```

`send` also accepts a dict, so you can pass the whole message as one object:

```python
client.emails.send({
    "from_": "hello@yourdomain.com",
    "to": ["you@example.com"],
    "subject": "Hello from Gosent",
    "text": "Your first email is on its way.",
})
```

## Send a raw MIME message

```python
mime = "\r\n".join([
    "From: hello@yourdomain.com",
    "To: you@example.com",
    "Subject: Hello from Gosent",
    "",
    "Your first email is on its way.",
])

result = client.emails.send_mime(mime)
```

## Field mapping

The friendly fields map onto the Send API wire format (`docs/sending-contract.md` §4):

| SDK | API |
| --- | --- |
| `from_` | `sender` |
| `to`, `cc`, `bcc` | arrays of the same name (a string becomes a one-element array) |
| `html` | `html_body` |
| `text` | `text_body` |
| `reply_to` | a `Reply-To` entry in `custom_headers` |
| `headers` | `custom_headers` |
| `attachments[].filename` | `attachments[].filename` |
| `attachments[].content` | `attachments[].fileblob` (base64 of the UTF-8 string, or raw `bytes`) |
| `attachments[].content_type` | `attachments[].mimetype` |

`from_` and `to` are required. `html` and `text` are both optional, but the API needs at
least one of them.

## Handling errors

`send` and `send_mime` raise `gosent.GosentError` when the API refuses the request or the
transport fails:

```python
try:
    result = client.emails.send(from_="hello@yourdomain.com", to="you@example.com", text="Hi")
except gosent.GosentError as err:
    print(err.status_code)   # e.g. 401
    print(err.code)          # e.g. "API_KEY_INVALID" (the E_ApiResponseCodes. prefix is stripped)
    print(err.message)       # human readable
    print(err.request_id)    # the request_id from the envelope, when present
    print(err.retry_after)   # the Retry-After header on a 429, when present
    print(err.field_errors)  # {"sender": "..."} on a 400 validation error
```

On success `SendResult` carries the per-recipient outcome:

```python
result.succeeded        # number accepted
result.failed           # number refused
result.failures         # refused addresses
result.failure_details  # [FailureDetail(recipient, reason, error_code)]
result.email_id         # the email_id for this send
result.sandboxed        # True only when the API key is in sandbox mode
```

A transport failure (DNS, connection refused, timeout) raises `GosentError` with
`code == "network_error"` and `status_code == 0`. A local misuse (missing `from_`, a
forbidden custom header, a non-string MIME body) raises `ValueError` before any request.

Common status codes: `400` bad payload, `401` missing or invalid key, `403` suspended or
unauthorized account, `429` monthly limit reached (check `err.retry_after`), `500`
server error.

## Sandbox and verified sender

The `From` domain must be a verified sender domain on your account, otherwise the API
answers `400` (`SENDER_NOT_VERIFIED`). While a key is in sandbox mode, `result.sandboxed`
is `True` and the message is accepted without delivery.

## License

UNLICENSED.
