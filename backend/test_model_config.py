"""
Model Configuration Verification Test Suite

Verifies:
1. Default CEO model resolves to 'google/gemma-3-27b-it'.
2. Default SMART_MODEL and FALLBACK_MODEL resolve to 'google/gemma-3-27b-it'.
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import MODEL_MAP, SMART_MODEL, FALLBACK_MODEL


class TestModelConfig(unittest.TestCase):

    def test_default_model_configuration(self):
        """Verify default CEO, SMART, and FALLBACK models use available free OpenRouter slug."""
        self.assertEqual(MODEL_MAP.get("ceo"), "google/gemma-3-27b-it")
        self.assertEqual(SMART_MODEL, "google/gemma-3-27b-it")
        self.assertEqual(FALLBACK_MODEL, "google/gemma-3-27b-it")
        print("[PASS] Default model configuration verified: google/gemma-3-27b-it")


if __name__ == "__main__":
    unittest.main()
