"""
Model Configuration Verification Test Suite

Verifies:
1. Default CEO model, SMART_MODEL, and FALLBACK_MODEL resolve to 'openrouter/free'.
2. resolve_model_name normalizes legacy paid model slugs (like 'google/gemma-3-27b-it' or 'google/gemini-2.5-flash') to 'openrouter/free'.
3. resolve_model_name appends ':free' to unspecified vendor model slugs on OpenRouter.
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import MODEL_MAP, SMART_MODEL, FALLBACK_MODEL
from app.agents.engine import resolve_model_name


class TestModelConfig(unittest.TestCase):

    def test_default_model_configuration(self):
        """Verify default CEO, SMART, and FALLBACK models use openrouter/free."""
        self.assertEqual(MODEL_MAP.get("ceo"), "openrouter/free")
        self.assertEqual(SMART_MODEL, "openrouter/free")
        self.assertEqual(FALLBACK_MODEL, "openrouter/free")
        print("[PASS] Default model configuration verified: openrouter/free")

    def test_model_resolution_logic(self):
        """Verify resolve_model_name normalizes legacy or paid slugs for OpenRouter free tier."""
        self.assertEqual(resolve_model_name("google/gemma-3-27b-it", "openrouter"), "openrouter/free")
        self.assertEqual(resolve_model_name("google/gemini-2.5-flash", "openrouter"), "openrouter/free")
        self.assertEqual(resolve_model_name("openrouter/free", "openrouter"), "openrouter/free")
        self.assertEqual(resolve_model_name("meta-llama/llama-3.3-70b-instruct", "openrouter"), "meta-llama/llama-3.3-70b-instruct:free")
        self.assertEqual(resolve_model_name("gpt-4o", "openai"), "gpt-4o")
        print("[PASS] Model resolution logic verified for all provider scenarios.")


if __name__ == "__main__":
    unittest.main()
