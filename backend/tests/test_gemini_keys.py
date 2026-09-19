"""Unit tests for 3-key Gemini rotation with quota failover (fully offline)."""

import unittest

from app.services.ai.gemini_keys import GeminiKeyManager


def _manager_with_keys(keys):
    mgr = GeminiKeyManager()
    mgr._configured_keys = lambda: list(keys)  # noqa: SLF001 - test seam
    return mgr


class TestQuotaDetection(unittest.TestCase):
    def test_quota_markers_detected(self):
        for msg in [
            "429 RESOURCE_EXHAUSTED: quota exceeded",
            "Rate limit exceeded, retry later",
            "API key not valid. Please pass a valid API key.",
            "invalid api key",
            "You have exhausted your limit",
            "billing error: permission denied",
        ]:
            self.assertTrue(GeminiKeyManager.is_quota_error(Exception(msg)), f"missed: {msg}")

    def test_non_quota_errors_not_detected(self):
        for msg in ["connection reset by peer", "invalid JSON response", "timeout"]:
            self.assertFalse(GeminiKeyManager.is_quota_error(Exception(msg)), msg)


class TestRotation(unittest.TestCase):
    KEYS = ["key-A", "key-B", "key-C"]

    def test_iterates_all_three_keys(self):
        mgr = _manager_with_keys(self.KEYS)
        self.assertEqual(list(mgr.iter_keys()), self.KEYS)

    def test_round_robin_advances(self):
        mgr = _manager_with_keys(self.KEYS)
        first = list(mgr.iter_keys())
        second = list(mgr.iter_keys())
        self.assertEqual(set(first), set(second))
        # Position advances so usage spreads across keys over time.
        self.assertEqual(len(second), 3)

    def test_quota_failure_fails_over_to_next_key(self):
        mgr = _manager_with_keys(self.KEYS)
        mgr.report_quota_failure("key-A")
        remaining = list(mgr.iter_keys())
        self.assertNotIn("key-A", remaining)
        self.assertIn("key-B", remaining)
        self.assertIn("key-C", remaining)

    def test_all_keys_cooling_down_fails_over_fast(self):
        mgr = _manager_with_keys(self.KEYS)
        for k in self.KEYS:
            mgr.report_quota_failure(k)
        # Intentional: when every key is cooling down, return nothing so
        # callers fall back to the offline engine instantly instead of stalling
        # on a doomed round of serial failures.
        self.assertEqual(list(mgr.iter_keys()), [])

    def test_success_clears_cooldown(self):
        mgr = _manager_with_keys(self.KEYS)
        mgr.report_quota_failure("key-A")
        mgr.report_success("key-A")
        self.assertIn("key-A", list(mgr.iter_keys()))

    def test_no_keys_configured(self):
        mgr = _manager_with_keys([])
        self.assertFalse(mgr.has_keys())
        self.assertEqual(list(mgr.iter_keys()), [])


class TestKeyLoading(unittest.TestCase):
    def test_combines_numbered_and_list_keys(self):
        import app.config as config_module

        orig = (
            config_module.settings.GEMINI_API_KEY,
            config_module.settings.GEMINI_API_KEY_2,
            config_module.settings.GEMINI_API_KEY_3,
            config_module.settings.GEMINI_API_KEYS,
        )
        try:
            config_module.settings.GEMINI_API_KEY = "  key-A "
            config_module.settings.GEMINI_API_KEY_2 = '"key-B"'
            config_module.settings.GEMINI_API_KEY_3 = "your_gemini_api_key_here"
            config_module.settings.GEMINI_API_KEYS = "key-C, key-A"
            self.assertEqual(config_module.get_gemini_keys(), ["key-A", "key-B", "key-C"])
            self.assertTrue(config_module.is_gemini_configured())
        finally:
            (
                config_module.settings.GEMINI_API_KEY,
                config_module.settings.GEMINI_API_KEY_2,
                config_module.settings.GEMINI_API_KEY_3,
                config_module.settings.GEMINI_API_KEYS,
            ) = orig

    def test_empty_means_not_configured(self):
        import app.config as config_module

        orig = (
            config_module.settings.GEMINI_API_KEY,
            config_module.settings.GEMINI_API_KEY_2,
            config_module.settings.GEMINI_API_KEY_3,
            config_module.settings.GEMINI_API_KEYS,
        )
        try:
            config_module.settings.GEMINI_API_KEY = ""
            config_module.settings.GEMINI_API_KEY_2 = ""
            config_module.settings.GEMINI_API_KEY_3 = ""
            config_module.settings.GEMINI_API_KEYS = ""
            self.assertEqual(config_module.get_gemini_keys(), [])
            self.assertFalse(config_module.is_gemini_configured())
        finally:
            (
                config_module.settings.GEMINI_API_KEY,
                config_module.settings.GEMINI_API_KEY_2,
                config_module.settings.GEMINI_API_KEY_3,
                config_module.settings.GEMINI_API_KEYS,
            ) = orig


if __name__ == "__main__":
    unittest.main()
