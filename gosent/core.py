"""Wire mapping and transport for the Gosent Send API (docs/sending-contract.md §4).

Standard library only: everything below is buildable on Python 3.9 with no pip
install. The mapping mirrors the server exactly:

    from -> sender        html -> html_body       text -> text_body
    replyTo -> Reply-To custom header             attachments -> fileblob (base64)
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

VERSION = "0.1.0"
DEFAULT_BASE_URL = "https://api.gosent.net/v3/"
ERROR_CODE_PREFIX = "E_ApiResponseCodes."

# Mirrors apps/api/app/send_api.py FORBIDDEN_HEADERS/FORBIDDEN_PREFIXES.
FORBIDDEN_HEADERS = frozenset(
    {
        "from", "to", "cc", "bcc", "sender", "return-path", "received",
        "dkim-signature", "message-id", "date", "mime-version",
    }
)
FORBIDDEN_PREFIXES = ("content-", "x-gosent-")


class GosentError(Exception):
    """An API or transport error, flattened from the SMTP2GO-style envelope."""

    def __init__(
        self,
        status_code,
        code,
        message,
        request_id=None,
        retry_after=None,
        field_errors=None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.retry_after = retry_after
        self.field_errors = field_errors or {}

    def __repr__(self):
        return "GosentError(status_code={0!r}, code={1!r}, message={2!r})".format(
            self.status_code, self.code, self.message
        )


def normalize_base_url(base_url):
    raw = (base_url or DEFAULT_BASE_URL).strip()
    return raw if raw.endswith("/") else raw + "/"


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _assert_header_allowed(name):
    lower = name.lower()
    if lower in FORBIDDEN_HEADERS or lower.startswith(FORBIDDEN_PREFIXES):
        raise ValueError(
            "Header {0!r} may not be set via headers; use the top-level field.".format(name)
        )


def _custom_headers(params):
    out = []
    reply_to = params.get("reply_to")
    if reply_to:
        out.append({"header": "Reply-To", "value": str(reply_to)})
    for key, value in (params.get("headers") or {}).items():
        _assert_header_allowed(key)
        out.append({"header": key, "value": "" if value is None else str(value)})
    return out


def _attachment(att):
    if not isinstance(att, dict):
        raise ValueError("Each attachment must be a dict.")
    filename = att.get("filename")
    if not filename:
        raise ValueError("attachment['filename'] is required.")
    content = att.get("content", "")
    if isinstance(content, str):
        blob = base64.b64encode(content.encode("utf-8")).decode("ascii")
    elif isinstance(content, (bytes, bytearray)):
        blob = base64.b64encode(bytes(content)).decode("ascii")
    else:
        raise ValueError("attachment['content'] must be str or bytes.")
    mimetype = att.get("content_type") or att.get("contentType")
    if not mimetype:
        lower = str(filename).lower()
        if lower.endswith(".txt"):
            mimetype = "text/plain"
        elif lower.endswith(".html"):
            mimetype = "text/html"
        elif lower.endswith(".json"):
            mimetype = "application/json"
        else:
            mimetype = "application/octet-stream"
    return {"filename": str(filename), "fileblob": blob, "mimetype": mimetype}


def map_params(params):
    """Friendly params -> the wire object the API expects (contract §4.1)."""
    sender = params.get("from") or params.get("from_")
    to = _as_list(params.get("to"))
    if not sender:
        raise ValueError("'from_' is required.")
    if not to:
        raise ValueError("'to' is required.")
    payload = {"sender": str(sender), "to": to}
    for friendly, field in (("cc", "cc"), ("bcc", "bcc")):
        values = _as_list(params.get(friendly))
        if values:
            payload[field] = values
    if params.get("subject"):
        payload["subject"] = str(params["subject"])
    if params.get("html"):
        payload["html_body"] = str(params["html"])
    if params.get("text"):
        payload["text_body"] = str(params["text"])
    headers = _custom_headers(params)
    if headers:
        payload["custom_headers"] = headers
    attachments = params.get("attachments") or []
    if attachments:
        payload["attachments"] = [_attachment(a) for a in attachments]
    return payload


def _strip_error_code(code):
    if code.startswith(ERROR_CODE_PREFIX):
        return code[len(ERROR_CODE_PREFIX):]
    return code


def _parse_envelope(body):
    try:
        envelope = json.loads(body)
    except ValueError:
        raise ValueError("The server sent a non-JSON envelope.")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
        raise ValueError("The server sent an envelope without a data object.")
    return envelope


def _error_from(status_code, envelope, retry_after=None):
    data = envelope.get("data") or {}
    validation = data.get("field_validation_errors") or {}
    field_errors = {}
    if validation:
        field_name = validation.get("fieldname")
        if field_name:
            field_errors[field_name] = validation.get("message", "")
    return GosentError(
        status_code=status_code,
        code=_strip_error_code(str(data.get("error_code") or "UNKNOWN_ERROR")),
        message=str(data.get("error") or "Request failed with status {0}".format(status_code)),
        request_id=envelope.get("request_id") or None,
        retry_after=retry_after,
        field_errors=field_errors,
    )


def request_send(endpoint, api_key, base_url, payload, timeout=30):
    """POST to /v3/email/<endpoint>; returns the `data` dict or raises GosentError."""
    url = "{0}email/{1}".format(base_url, endpoint)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Gosent-Sdk": "gosent-python/{0}".format(VERSION),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.status
            raw = response.read()
            header_retry = response.headers.get("Retry-After")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read()
        header_retry = exc.headers.get("Retry-After") if exc.headers else None
    except (urllib.error.URLError, OSError) as exc:
        raise GosentError(0, "network_error", str(getattr(exc, "reason", exc)))

    try:
        envelope = _parse_envelope(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise GosentError(status_code, "network_error", str(exc))

    if 200 <= status_code < 300:
        return envelope["data"]
    raise _error_from(status_code, envelope, header_retry)
