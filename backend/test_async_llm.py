import os
import sys
import time
import asyncio
import unittest
from unittest.mock import patch, MagicMock

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.agents.engine import _llm_call_single, _llm_call_with_retry, AGENT_TIMEOUTS, _sanitize_error
from app.models.schemas import AgentRole


class MockChoiceMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockChoiceMessage(content)

class MockCompletionResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]


class TestP43AsyncLLMExecution(unittest.IsolatedAsyncioTestCase):

    async def test_case_a_single_call_success(self):
        """CASE A: One agent call completes successfully -> structured response returned."""
        mock_client = MagicMock()
        async def mock_async_create(*args, **kwargs):
            return MockCompletionResponse('{"status": "SUCCESS", "analysis": "Async execution working"}')

        mock_client.chat.completions.create = mock_async_create

        with patch("app.agents.engine.get_client", return_value=mock_client):
            res, model_used = await _llm_call_with_retry(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=100,
                timeout=10,
                provider="openrouter"
            )
            self.assertIn("SUCCESS", res)
            self.assertEqual(model_used, "openrouter/gpt-4o")
        print("[PASS] CASE A (Single Async LLM Call Success) PASSED.")

    async def test_case_b_llm_failure_handling(self):
        """CASE B: LLM call raises an error -> structured exception returned, API key sanitized."""
        mock_client = MagicMock()
        async def mock_failing_create(*args, **kwargs):
            raise RuntimeError("API Error with secret key: sk-proj1234567890abcdef1234567890")

        mock_client.chat.completions.create = mock_failing_create

        with patch("app.agents.engine.get_client", return_value=mock_client):
            with self.assertRaises(RuntimeError) as ctx:
                await _llm_call_with_retry(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hello"}],
                    max_tokens=100,
                    timeout=5,
                    provider="openrouter"
                )
            err_msg = str(ctx.exception)
            self.assertIn("LLM call failed on all keys", err_msg)
            self.assertNotIn("sk-proj1234567890abcdef1234567890", err_msg)
            self.assertIn("[REDACTED_API_KEY]", err_msg)
        print("[PASS] CASE B (Structured LLM Error Handling & API Key Redaction) PASSED.")

    async def test_case_c_concurrency_benchmark(self):
        """CASE C: Concurrent vs Sequential LLM Execution Benchmark."""
        mock_client = MagicMock()
        delay = 0.5  # Simulate 500ms network latency per call

        async def mock_delayed_create(*args, **kwargs):
            await asyncio.sleep(delay)
            return MockCompletionResponse('{"result": "delayed_ok"}')

        mock_client.chat.completions.create = mock_delayed_create

        with patch("app.agents.engine.get_client", return_value=mock_client):
            # 1. Sequential Execution
            start_seq = time.time()
            res1, _ = await _llm_call_with_retry("gpt-4o", [{"role": "user", "content": "call 1"}], 100, 5)
            res2, _ = await _llm_call_with_retry("gpt-4o", [{"role": "user", "content": "call 2"}], 100, 5)
            dur_seq = time.time() - start_seq

            # 2. Concurrent Execution
            start_conc = time.time()
            task1 = _llm_call_with_retry("gpt-4o", [{"role": "user", "content": "call 1"}], 100, 5)
            task2 = _llm_call_with_retry("gpt-4o", [{"role": "user", "content": "call 2"}], 100, 5)
            results = await asyncio.gather(task1, task2)
            dur_conc = time.time() - start_conc

            improvement = ((dur_seq - dur_conc) / dur_seq) * 100.0

            print("\n" + "=" * 60)
            print("P4.3 LLM CONCURRENCY BENCHMARK RESULTS")
            print("=" * 60)
            print(f"Sequential Execution Duration : {dur_seq:.3f}s (2 x {delay:.1f}s)")
            print(f"Concurrent Execution Duration : {dur_conc:.3f}s (Parallel asyncio.gather)")
            print(f"Approximate Improvement       : {improvement:.1f}% speedup")
            print("=" * 60)

            # Concurrent duration should take ~1x delay instead of ~2x delay
            self.assertLess(dur_conc, dur_seq * 0.75)
            self.assertEqual(len(results), 2)
        print("[PASS] CASE C (Concurrent LLM Concurrency Benchmark) PASSED.")

    async def test_event_loop_responsiveness_heartbeat(self):
        """Verify event-loop safety: Heartbeat task continues ticking while LLM call is pending."""
        heartbeat_ticks = 0
        heartbeat_running = True

        async def heartbeat():
            nonlocal heartbeat_ticks, heartbeat_running
            while heartbeat_running:
                heartbeat_ticks += 1
                await asyncio.sleep(0.05)  # 50ms tick

        mock_client = MagicMock()
        async def mock_pending_create(*args, **kwargs):
            await asyncio.sleep(0.6)  # 600ms simulated LLM call
            return MockCompletionResponse('{"status": "DONE"}')

        mock_client.chat.completions.create = mock_pending_create

        hb_task = asyncio.create_task(heartbeat())
        try:
            with patch("app.agents.engine.get_client", return_value=mock_client):
                res, _ = await _llm_call_with_retry("gpt-4o", [{"role": "user", "content": "test"}], 100, 5)
                self.assertIn("DONE", res)
        finally:
            heartbeat_running = False
            await hb_task

        print(f"[PASS] Event-Loop Safety Verified: Heartbeat ticked {heartbeat_ticks} times during 600ms LLM call.")
        self.assertGreaterEqual(heartbeat_ticks, 8)


if __name__ == "__main__":
    unittest.main()
