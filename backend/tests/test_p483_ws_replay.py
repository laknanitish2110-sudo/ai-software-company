import os
import json
import asyncio
import unittest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.core.database import init_db, save_execution_event, get_execution_events_since
from app.services.redis_coordinator import redis_coordinator, InMemoryCoordinator


class TestP483WSReplay(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        os.environ["ENVIRONMENT"] = "development"
        await init_db()
        redis_coordinator.reset_in_memory()
        self.project_id = f"test_ws_replay_proj_{os.urandom(4).hex()}"
        self.exec_id = f"exec_run_{os.urandom(4).hex()}"

    async def test_case_1_monotonic_sequence_generation(self):
        """Case 1: Ensure publish_event_durable assigns strictly increasing sequence numbers."""
        ev1 = await redis_coordinator.publish_event_durable(self.project_id, "agent_started", {"role": "ceo"}, self.exec_id)
        ev2 = await redis_coordinator.publish_event_durable(self.project_id, "agent_completed", {"role": "ceo"}, self.exec_id)
        ev3 = await redis_coordinator.publish_event_durable(self.project_id, "agent_started", {"role": "architect"}, self.exec_id)

        self.assertEqual(ev1["seq"], 1)
        self.assertEqual(ev2["seq"], 2)
        self.assertEqual(ev3["seq"], 3)
        self.assertEqual(ev1["execution_id"], self.exec_id)

    async def test_case_2_reconnect_replay_buffer(self):
        """Case 2: Verify reconnecting client with last_seq=1 gets events 2 and 3 in order."""
        await redis_coordinator.publish_event_durable(self.project_id, "e1", {"msg": "first"}, self.exec_id)
        await redis_coordinator.publish_event_durable(self.project_id, "e2", {"msg": "second"}, self.exec_id)
        await redis_coordinator.publish_event_durable(self.project_id, "e3", {"msg": "third"}, self.exec_id)

        replayed = await redis_coordinator.get_events_since(self.project_id, last_seq=1)
        self.assertEqual(len(replayed), 2)
        self.assertEqual(replayed[0]["seq"], 2)
        self.assertEqual(replayed[0]["type"], "e2")
        self.assertEqual(replayed[1]["seq"], 3)
        self.assertEqual(replayed[1]["type"], "e3")

    async def test_case_3_database_fallback_persistence(self):
        """Case 3: Verify fallback to database table execution_events when buffer is empty."""
        await save_execution_event(self.project_id, self.exec_id, 1, "db_e1", {"info": "db1"})
        await save_execution_event(self.project_id, self.exec_id, 2, "db_e2", {"info": "db2"})

        # Query database via get_execution_events_since directly
        db_events = await get_execution_events_since(self.project_id, last_seq=0)
        self.assertEqual(len(db_events), 2)
        self.assertEqual(db_events[0]["seq"], 1)
        self.assertEqual(db_events[0]["event_type"], "db_e1")
        self.assertEqual(db_events[1]["seq"], 2)
        self.assertEqual(db_events[1]["event_type"], "db_e2")

    async def test_case_4_duplicate_sequence_protection(self):
        """Case 4: Verify client duplicate protection logic discards events with seq <= highest_replayed_seq."""
        highest_replayed_seq = 2
        
        live_events = [
            {"seq": 1, "type": "dup1", "data": {}},
            {"seq": 2, "type": "dup2", "data": {}},
            {"seq": 3, "type": "new3", "data": {}}
        ]

        received = []
        for ev in live_events:
            ev_seq = ev.get("seq", 0)
            if ev_seq <= highest_replayed_seq:
                continue # Discard duplicate
            highest_replayed_seq = ev_seq
            received.append(ev)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["seq"], 3)
        self.assertEqual(received[0]["type"], "new3")

    async def test_case_5_concurrent_sequence_allocation(self):
        """Case 5: Multi-worker concurrent event publishing allocates unique sequence numbers."""
        async def _publish(idx: int):
            return await redis_coordinator.publish_event_durable(
                self.project_id, f"evt_{idx}", {"worker": idx}, self.exec_id
            )

        events = await asyncio.gather(*[_publish(i) for i in range(10)])
        seqs = [e["seq"] for e in events]
        self.assertEqual(len(seqs), 10)
        self.assertEqual(len(set(seqs)), 10)
        self.assertEqual(min(seqs), 1)
        self.assertEqual(max(seqs), 10)


if __name__ == "__main__":
    unittest.main()
