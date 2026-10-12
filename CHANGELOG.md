# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added

- `gosent.Gosent` client. The API key comes from `api_key` or the `GOSENT_API_KEY`
  environment variable; the base URL from `base_url`, `GOSENT_API_BASE_URL`, or the
  default `https://api.gosent.net/v3/`.
- `client.emails.send(...)` for `POST /v3/email/send`, with `from_`, `to`, `cc`, `bcc`,
  `subject`, `html`, `text`, `reply_to`, custom `headers` and `attachments`, passed as
  keyword arguments or as a single dict.
- Attachments from `str` or `bytes`, base64-encoded by the SDK, with the MIME type guessed
  from the file name when `content_type` is not given.
- `client.emails.send_mime(mime)` for `POST /v3/email/mime`.
- `SendResult` and `FailureDetail` with the per-recipient outcome, `email_id` and
  `sandboxed`.
- `GosentError` with `status_code`, `code` (without the `E_ApiResponseCodes.` prefix),
  `message`, `request_id`, `retry_after` and `field_errors`. Transport failures use
  `code="network_error"` and `status_code=0`.
- Local checks that raise `ValueError` before any request: missing API key, missing
  `from_` or `to`, headers the API sets itself, malformed attachments, an empty MIME
  message.
- `X-Gosent-Sdk: gosent-python/<version>` header on every request.
- Standard library only, Python 3.9 or newer, MIT license.

[0.1.0]: https://github.com/sadewadee/gosent-python/tree/v0.1.0
