# gosent

Official Python SDK for the [Gosent](https://gosent.net) Send API. Send email with a few
lines of code.

Standard library only: no runtime dependencies. Requires Python 3.9 or newer.

## Install

```sh
pip install gosent
```

## Quick start

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

The sender argument is `from_`, with a trailing underscore, because `from` is a reserved
word in Python.

The API key defaults to the `GOSENT_API_KEY` environment variable when you omit it:

```python
client = gosent.Gosent()
```

## Sending email

`client.emails.send(...)` accepts these keyword arguments:

| Argument | Type | Notes |
| --- | --- | --- |
| `from_` | `str` | Required. The sender address. |
| `to` | `str` or list of `str` | Required. A single string becomes a one-element list. |
| `subject` | `str` | |
| `html` | `str` | HTML body. |
| `text` | `str` | Plain text body. |
| `cc`, `bcc` | `str` or list of `str` | |
| `reply_to` | `str` | Sent as a `Reply-To` header. |
| `headers` | `dict` | Extra custom headers, for example `{"X-Campaign": "welcome"}`. |
| `attachments` | list of `dict` | See [Attachments](#attachments). |

`html` and `text` are both optional, but the API needs at least one of them.

```python
result = client.emails.send(
    from_="hello@yourdomain.com",
    to=["ana@example.com", "budi@example.com"],
    cc="team@example.com",
    reply_to="support@yourdomain.com",
    subject="Your receipt",
    html="<p>Thanks for your order.</p>",
    text="Thanks for your order.",
    headers={"X-Campaign": "receipts"},
)
```

`send` also accepts a dict as its first argument, so you can pass the whole message as one
object:

```python
client.emails.send({
    "from_": "hello@yourdomain.com",
    "to": ["you@example.com"],
    "subject": "Hello from Gosent",
    "text": "Your first email is on its way.",
})
```

### Attachments

Each attachment is a dict with:

- `filename` (required);
- `content`: a `str` (sent as its UTF-8 bytes) or `bytes`;
- `content_type` (optional): when omitted it is guessed from the file name: `.txt` is
  `text/plain`, `.html` is `text/html`, `.json` is `application/json`, anything else is
  `application/octet-stream`.

The SDK base64-encodes the content for you.

```python
client.emails.send(
    from_="hello@yourdomain.com",
    to="you@example.com",
    subject="Monthly report",
    text="The report is attached.",
    attachments=[
        {"filename": "notes.txt", "content": "Meeting at 10."},
        {"filename": "report.csv", "content": b"id,total\n1,42\n", "content_type": "text/csv"},
    ],
)
```

### Custom headers

Headers the API sets itself cannot be passed in `headers`: `From`, `To`, `Cc`, `Bcc`,
`Sender`, `Return-Path`, `Received`, `DKIM-Signature`, `Message-ID`, `Date`,
`MIME-Version`, and any header starting with `Content-` or `X-Gosent-`. Passing one raises
`ValueError` before any request is made. Use the top-level arguments (`from_`, `to`,
`reply_to`, ...) instead.

### Wire format

The SDK maps its arguments onto the Send API request body:

| SDK | API |
| --- | --- |
| `from_` | `sender` |
| `to`, `cc`, `bcc` | arrays of the same name |
| `html` | `html_body` |
| `text` | `text_body` |
| `reply_to` | a `Reply-To` entry in `custom_headers` |
| `headers` | `custom_headers` |
| `attachments[].filename` | `attachments[].filename` |
| `attachments[].content` | `attachments[].fileblob` (base64) |
| `attachments[].content_type` | `attachments[].mimetype` |

## Send a raw MIME message

`client.emails.send_mime(mime)` sends a message you built yourself. Pass the MIME message
as a string, either raw text or base64. It is posted to `/v3/email/mime`.

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

An empty or non-string `mime` raises `ValueError` before any request is made.

## The result

`send` and `send_mime` return a `gosent.SendResult`:

```python
result.succeeded        # number of recipients accepted
result.failed           # number of recipients refused
result.failures         # refused addresses
result.failure_details  # list of gosent.FailureDetail(recipient, reason, error_code)
result.email_id         # the email_id for this send
result.sandboxed        # True in sandbox mode, False when not, None when not reported
```

A send where some recipients are refused still returns a `SendResult`; check
`result.failed` and `result.failure_details`.

## Handling errors

`send` and `send_mime` raise `gosent.GosentError` when the API refuses the request or the
transport fails:

```python
try:
    result = client.emails.send(from_="hello@yourdomain.com", to="you@example.com", text="Hi")
except gosent.GosentError as err:
    print(err.status_code)   # HTTP status, for example 401 (0 for a network failure)
    print(err.code)          # for example "API_KEY_INVALID"
    print(err.message)       # human readable message
    print(err.request_id)    # the request_id from the response, or None
    print(err.retry_after)   # the Retry-After header as a string, or None
    print(err.field_errors)  # for example {"sender": "..."} on a 400 validation error
```

`err.code` is the API error code with its `E_ApiResponseCodes.` prefix removed.

A transport failure (DNS, connection refused, timeout) raises `GosentError` with
`code == "network_error"` and `status_code == 0`. A response that is not a valid JSON
envelope also raises `GosentError` with `code == "network_error"`, and `status_code` set
to the HTTP status.

A local mistake (missing API key, missing `from_` or `to`, a forbidden custom header, an
empty MIME message, a malformed attachment) raises `ValueError` before any request is
made.

Common status codes:

| Status | Meaning |
| --- | --- |
| `400` | Invalid payload, or the sender domain is not verified (`SENDER_NOT_VERIFIED`) |
| `401` | Missing or invalid API key |
| `403` | Suspended or unauthorized account |
| `429` | Monthly limit reached; check `err.retry_after` |
| `500` | Server error |

## Sandbox and verified sender

The `from_` domain must be a verified sender domain on your account, otherwise the API
answers `400` with code `SENDER_NOT_VERIFIED`. While a key is in sandbox mode,
`result.sandboxed` is `True` and the message is accepted without delivery.

## Configuration

```python
client = gosent.Gosent(
    api_key="...",                          # default: the GOSENT_API_KEY environment variable
    base_url="https://api.gosent.net/v3/",  # default: GOSENT_API_BASE_URL, then this URL
)
```

- `api_key`: your Gosent API key. When omitted, `GOSENT_API_KEY` is used. If neither is
  set, `Gosent()` raises `ValueError`.
- `base_url`: the Send API base URL. When omitted, `GOSENT_API_BASE_URL` is used, then
  `https://api.gosent.net/v3/`. A missing trailing slash is added.

Each request times out after 30 seconds. The timeout is not configurable in this version.

## Requirements

- Python 3.9 or newer.
- No third-party packages: the SDK uses only the Python standard library.

## Documentation

- Gosent documentation: https://gosent.net/docs
- SDK guide: https://gosent.net/docs/sdks

## License

MIT. See [LICENSE](LICENSE).
