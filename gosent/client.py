"""The Gosent client: `client.emails.send(...)` and `client.emails.send_mime(...)`."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import map_params, normalize_base_url, request_send


@dataclass
class FailureDetail:
    """One refused recipient (contract §4.1)."""

    recipient: str
    reason: str
    error_code: str


@dataclass
class SendResult:
    """The parsed `data` on a 2xx send."""

    succeeded: int
    failed: int
    failures: List[str] = field(default_factory=list)
    failure_details: List[FailureDetail] = field(default_factory=list)
    email_id: str = ""
    sandboxed: Optional[bool] = None


def _to_result(data: Dict[str, Any]) -> SendResult:
    details = []
    for item in data.get("failure_details") or []:
        if isinstance(item, dict):
            details.append(
                FailureDetail(
                    recipient=str(item.get("recipient", "")),
                    reason=str(item.get("reason", "")),
                    error_code=str(item.get("error_code", "")),
                )
            )
    sandboxed = data.get("sandboxed")
    return SendResult(
        succeeded=int(data.get("succeeded") or 0),
        failed=int(data.get("failed") or 0),
        failures=[str(item) for item in (data.get("failures") or [])],
        failure_details=details,
        email_id=str(data.get("email_id") or ""),
        sandboxed=None if sandboxed is None else bool(sandboxed),
    )


class _Emails:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url

    def send(self, from_=None, to=None, subject=None, html=None, text=None,
             cc=None, bcc=None, reply_to=None, headers=None, attachments=None,
             **kwargs) -> SendResult:
        """Send one email. Accepts a dict as the first argument, or kwargs."""
        if isinstance(from_, dict):
            params = dict(from_)
            params.update(kwargs)
        else:
            params = {
                "from": from_,
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "cc": cc,
                "bcc": bcc,
                "reply_to": reply_to,
                "headers": headers,
                "attachments": attachments,
            }
            params.update(kwargs)
        payload = map_params(params)
        return _to_result(request_send("send", self._api_key, self._base_url, payload))

    def send_mime(self, mime: str) -> SendResult:
        """Send a pre-built MIME message (raw text or base64)."""
        if not isinstance(mime, str) or not mime.strip():
            raise ValueError("The MIME message must be a non-empty string.")
        return _to_result(
            request_send("mime", self._api_key, self._base_url, {"mime_email": mime})
        )


class Gosent:
    """Gosent Send API client.

    ```python
    import gosent
    client = gosent.Gosent(api_key=os.environ["GOSENT_API_KEY"])
    result = client.emails.send(
        from_="hello@yourdomain.com",
        to="you@example.com",
        subject="Hello",
        html="<p>It works.</p>",
    )
    ```
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("GOSENT_API_KEY") or ""
        if not key:
            raise ValueError(
                "Missing API key. Pass api_key=... or set GOSENT_API_KEY."
            )
        self._base_url = normalize_base_url(base_url or os.environ.get("GOSENT_API_BASE_URL"))
        self.emails = _Emails(key, self._base_url)
