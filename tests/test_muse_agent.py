"""Offline tests for the Muse agent; no live Meta key or network needed."""
import os
import unittest
from unittest.mock import Mock, patch

from server.agent import MuseError, run_agent


class MuseAgentTests(unittest.TestCase):
    def setUp(self):
        self.tenant = {"id": "tenant_test", "pack": "front-desk"}
        self.env = patch.dict(os.environ, {"MODEL_API_KEY": "test-only-key", "META_MODEL": "muse-wonder-1.0"})
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch("server.agent.requests.post")
    def test_success(self, post):
        post.return_value = Mock(
            ok=True,
            json=lambda: {"output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": "Hello there"}]}
            ]},
        )
        self.assertEqual(run_agent(self.tenant, "sms", "caller", "Hi"), "Hello there")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["model"], "muse-wonder-1.0")
        self.assertEqual(kwargs["json"]["input"], "Hi")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-key")
        self.assertEqual(post.call_args.args[0], "https://api.meta.ai/v1/responses")

    @patch("server.agent.requests.post")
    def test_non_success_does_not_echo_provider_response(self, post):
        post.return_value = Mock(ok=False, status_code=403, text="sensitive body")
        with self.assertRaisesRegex(MuseError, "HTTP 403") as result:
            run_agent(self.tenant, "email", "caller", "private question")
        self.assertNotIn("sensitive", str(result.exception))

    @patch("server.agent.requests.post")
    def test_empty_output_is_error(self, post):
        post.return_value = Mock(ok=True, json=lambda: {"output": []})
        with self.assertRaisesRegex(MuseError, "no assistant text"):
            run_agent(self.tenant, "voice", "caller", "Hi")

    @patch("server.agent.requests.post")
    def test_missing_key_never_calls_provider(self, post):
        with patch.dict(os.environ, {"MODEL_API_KEY": ""}):
            with self.assertRaisesRegex(MuseError, "not configured"):
                run_agent(self.tenant, "sms", "caller", "Hi")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
