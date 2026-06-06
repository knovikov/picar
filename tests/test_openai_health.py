import json
import unittest


class FakeHTTPResponse:
    def __init__(self, status_code=200, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload or {"output_text": "OK"}

    def getcode(self):
        return self.status_code

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OpenAIHealthTests(unittest.TestCase):
    def test_extract_rate_limit_headers_keeps_remaining_and_reset_values(self):
        from kidbot.core.openai_health import extract_rate_limit_headers

        headers = {
            "x-ratelimit-limit-requests": "500",
            "x-ratelimit-remaining-requests": "499",
            "x-ratelimit-limit-tokens": "200000",
            "x-ratelimit-remaining-tokens": "199950",
            "x-ratelimit-reset-requests": "1s",
            "x-ratelimit-reset-tokens": "2m0s",
            "x-request-id": "req_123",
        }

        result = extract_rate_limit_headers(headers)

        self.assertEqual(result["remaining_requests"], "499")
        self.assertEqual(result["remaining_tokens"], "199950")
        self.assertEqual(result["reset_tokens"], "2m0s")
        self.assertEqual(result["request_id"], "req_123")

    def test_check_openai_key_returns_clear_message_when_key_missing(self):
        from kidbot.core.openai_health import check_openai_api_key

        result = check_openai_api_key("", model="gpt-5-mini")

        self.assertFalse(result.success)
        self.assertIn("не сохранен", result.message)

    def test_check_openai_key_uses_authorization_header_and_reports_limits(self):
        from kidbot.core.openai_health import check_openai_api_key

        captured = {}

        def requester(request, timeout):
            captured["authorization"] = request.headers["Authorization"]
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeHTTPResponse(
                headers={
                    "x-ratelimit-remaining-requests": "59",
                    "x-ratelimit-remaining-tokens": "149984",
                    "x-request-id": "req_ok",
                }
            )

        result = check_openai_api_key("sk-test-123", model="gpt-5-mini", requester=requester)

        self.assertTrue(result.success)
        self.assertEqual(captured["authorization"], "Bearer sk-test-123")
        self.assertEqual(captured["body"]["model"], "gpt-5-mini")
        self.assertEqual(result.rate_limits["remaining_requests"], "59")
        self.assertEqual(result.request_id, "req_ok")


if __name__ == "__main__":
    unittest.main()

