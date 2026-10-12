"""Unit tests for the Gosent Python SDK against a loopback stub.

Run: python -m pytest  (or)  python -m unittest discover -s tests
"""

import base64
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import gosent

KEY = "api-" + "P" * 40

SEEN = []
RESPONSE = {"status": 200, "envelope": None, "headers": {}}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence the stub
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        SEEN.append(
            {
                "url": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": json.loads(raw) if raw else None,
            }
        )
        body = json.dumps(RESPONSE["envelope"]).encode("utf-8")
        self.send_response(RESPONSE["status"])
        self.send_header("Content-Type", "application/json")
        for key, value in RESPONSE["headers"].items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def envelope(data, request_id="4c1f3d1a-test"):
    return {"request_id": request_id, "data": data}


def ok(succeeded=1, failed=0, **extra):
    data = {"succeeded": succeeded, "failed": failed, "failures": [],
            "failure_details": [], "email_id": "em_1"}
    data.update(extra)
    return envelope(data)


class StubCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:{0}/v3/".format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        SEEN.clear()
        RESPONSE.update({"status": 200, "envelope": ok(), "headers": {}})

    def client(self, key=KEY):
        return gosent.Gosent(api_key=key, base_url=self.base_url)


class TestSend(StubCase):
    def test_headers_and_mapped_body(self):
        RESPONSE["envelope"] = ok(email_id="em_42")
        result = self.client().emails.send(
            from_="hello@yourdomain.com",
            to=["a@example.com", "b@example.com"],
            subject="Hi",
            html="<p>ho</p>",
            text="ho",
            cc="c@example.com",
            reply_to="reply@yourdomain.com",
            headers={"X-Campaign": "welcome"},
        )
        self.assertEqual(result.email_id, "em_42")
        self.assertEqual(result.succeeded, 1)
        req = SEEN[0]
        self.assertEqual(req["url"], "/v3/email/send")
        self.assertEqual(req["headers"]["x-api-key"], KEY)
        self.assertIn("application/json", req["headers"]["content-type"])
        self.assertEqual(req["body"]["sender"], "hello@yourdomain.com")
        self.assertEqual(req["body"]["to"], ["a@example.com", "b@example.com"])
        self.assertEqual(req["body"]["cc"], ["c@example.com"])
        self.assertEqual(req["body"]["html_body"], "<p>ho</p>")
        self.assertEqual(req["body"]["text_body"], "ho")
        self.assertEqual(
            req["body"]["custom_headers"],
            [
                {"header": "Reply-To", "value": "reply@yourdomain.com"},
                {"header": "X-Campaign", "value": "welcome"},
            ],
        )

    def test_dict_form(self):
        self.client().emails.send(
            {"from_": "a@yourdomain.com", "to": "b@example.com", "text": "x"}
        )
        self.assertEqual(SEEN[0]["body"]["sender"], "a@yourdomain.com")
        self.assertEqual(SEEN[0]["body"]["to"], ["b@example.com"])

    def test_send_mime(self):
        RESPONSE["envelope"] = ok(email_id="em_mime")
        mime = "From: a@yourdomain.com\r\nTo: b@example.com\r\nSubject: M\r\n\r\nbody"
        result = self.client().emails.send_mime(mime)
        self.assertEqual(result.email_id, "em_mime")
        self.assertEqual(SEEN[0]["url"], "/v3/email/mime")
        self.assertEqual(SEEN[0]["body"]["mime_email"], mime)

    def test_sandboxed(self):
        RESPONSE["envelope"] = ok(sandboxed=True)
        self.assertTrue(self.client().emails.send(from_="a@yourdomain.com", to="b@example.com").sandboxed)

    def test_partial(self):
        RESPONSE["envelope"] = envelope(
            {
                "succeeded": 1,
                "failed": 1,
                "failures": ["bad@example.com"],
                "failure_details": [
                    {"recipient": "bad@example.com", "reason": "refused", "error_code": "INVALID_RECIPIENT"}
                ],
                "email_id": "em_part",
            }
        )
        result = self.client().emails.send(from_="a@yourdomain.com", to="b@example.com")
        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures, ["bad@example.com"])
        self.assertEqual(result.failure_details[0].recipient, "bad@example.com")
        self.assertEqual(result.failure_details[0].error_code, "INVALID_RECIPIENT")

    def test_attachments_base64_utf8(self):
        self.client().emails.send(
            from_="a@yourdomain.com",
            to="b@example.com",
            attachments=[{"filename": "catatan.txt", "content": "héllo"}],
        )
        att = SEEN[0]["body"]["attachments"][0]
        self.assertEqual(att["filename"], "catatan.txt")
        self.assertEqual(att["mimetype"], "text/plain")
        self.assertEqual(base64.b64decode(att["fileblob"]).decode("utf-8"), "héllo")


class TestErrors(StubCase):
    def _error(self):
        with self.assertRaises(gosent.GosentError) as ctx:
            self.client().emails.send(from_="a@yourdomain.com", to="b@example.com")
        return ctx.exception

    def test_400_field_errors(self):
        RESPONSE["status"] = 400
        RESPONSE["envelope"] = envelope(
            {
                "error_code": "E_ApiResponseCodes.NON_VALIDATING_IN_PAYLOAD",
                "error": "The request body is not valid.",
                "field_validation_errors": {"fieldname": "sender", "message": "bad sender"},
            }
        )
        err = self._error()
        self.assertEqual(err.status_code, 400)
        self.assertEqual(err.code, "NON_VALIDATING_IN_PAYLOAD")
        self.assertEqual(err.field_errors, {"sender": "bad sender"})

    def test_401(self):
        RESPONSE["status"] = 401
        RESPONSE["envelope"] = envelope(
            {"error_code": "E_ApiResponseCodes.API_KEY_INVALID", "error": "not valid"}
        )
        err = self._error()
        self.assertEqual(err.status_code, 401)
        self.assertEqual(err.code, "API_KEY_INVALID")

    def test_403(self):
        RESPONSE["status"] = 403
        RESPONSE["envelope"] = envelope(
            {"error_code": "E_ApiResponseCodes.ACCOUNT_SUSPENDED", "error": "suspended"}
        )
        err = self._error()
        self.assertEqual(err.status_code, 403)
        self.assertEqual(err.code, "ACCOUNT_SUSPENDED")

    def test_429_retry_after(self):
        RESPONSE["status"] = 429
        RESPONSE["headers"] = {"Retry-After": "3600"}
        RESPONSE["envelope"] = envelope(
            {"error_code": "E_ApiResponseCodes.MONTHLY_LIMIT_EXCEEDED", "error": "limit"}
        )
        err = self._error()
        self.assertEqual(err.status_code, 429)
        self.assertEqual(err.code, "MONTHLY_LIMIT_EXCEEDED")
        self.assertEqual(err.retry_after, "3600")

    def test_500(self):
        RESPONSE["status"] = 500
        RESPONSE["envelope"] = envelope(
            {"error_code": "E_ApiResponseCodes.INTERNAL_ERROR", "error": "boom"}
        )
        err = self._error()
        self.assertEqual(err.status_code, 500)
        self.assertEqual(err.code, "INTERNAL_ERROR")

    def test_network_error(self):
        client = gosent.Gosent(api_key=KEY, base_url="http://127.0.0.1:1/v3/")
        with self.assertRaises(gosent.GosentError) as ctx:
            client.emails.send(from_="a@yourdomain.com", to="b@example.com")
        self.assertEqual(ctx.exception.code, "network_error")
        self.assertEqual(ctx.exception.status_code, 0)


class TestParams(unittest.TestCase):
    def test_missing_key_raises(self):
        saved = os.environ.pop("GOSENT_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                gosent.Gosent()
        finally:
            if saved is not None:
                os.environ["GOSENT_API_KEY"] = saved

    def test_forbidden_headers(self):
        client = gosent.Gosent(api_key=KEY, base_url="http://127.0.0.1:1/v3/")
        for bad in ({"Content-Type": "x"}, {"X-Gosent-Api-Key-Id": "x"}, {"From": "x@y.z"}):
            with self.assertRaises(ValueError):
                client.emails.send(from_="a@yourdomain.com", to="b@example.com", headers=bad)


if __name__ == "__main__":
    unittest.main()
