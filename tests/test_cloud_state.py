"""No-network behaviour tests for the Firestore quota transaction boundary."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import threading
import unittest

from nuri.cloud_state import BUSY_ERROR, CloudState, LIMIT_ERROR, STATE_ERROR
from nuri.config import Settings
from nuri.models import UserError


class MemoryTransaction:
    def __init__(self, documents):
        self.documents = deepcopy(documents)
        self.wrote = False

    def get(self, name):
        if self.wrote:
            raise AssertionError("Firestore forbids reads after writes")
        return deepcopy(self.documents.get(name))

    def set(self, name, value):
        self.wrote = True
        self.documents[name] = deepcopy(value)


class AtomicMemoryBackend:
    """Serializable fake: applies an entire transaction or rolls all of it back."""

    def __init__(self):
        self.documents = {}
        self.lock = threading.Lock()
        self.fail_before_commit = False
        self.fail_after_commit = False

    def transact(self, callback):
        with self.lock:
            transaction = MemoryTransaction(self.documents)
            result = callback(transaction)
            if self.fail_before_commit:
                raise RuntimeError("private diagnostic text must not escape")
            self.documents = transaction.documents
            if self.fail_after_commit:
                raise RuntimeError("ambiguous network failure after commit")
            return result


class Clock:
    def __init__(self, now=None):
        self.now = now or datetime(2026, 10, 27, 1, tzinfo=timezone.utc).timestamp()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class CloudStateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.backend = AtomicMemoryBackend()
        self.settings = Settings(daily_request_limit=2)
        self.state = self.new_state()

    def new_state(self, settings=None):
        return CloudState(settings or self.settings, backend=self.backend, clock=self.clock)

    def attempts(self, day="2026-10-27"):
        return self.backend.documents.get(f"day_{day}", {}).get("attempts", 0)

    async def test_finished_duplicate_does_not_recharge_after_restart(self):
        self.assertTrue(await self.state.reserve("101"))
        await self.state.finish("101")
        self.clock.advance(20)
        self.assertFalse(await self.new_state().reserve("101"))
        self.assertEqual(self.attempts(), 1)

    async def test_crashed_reserved_request_never_reaches_provider_again(self):
        self.assertTrue(await self.state.reserve("102"))
        self.clock.advance(301)
        self.assertFalse(await self.new_state().reserve("102"))
        self.assertTrue(await self.new_state().reserve("103"))
        self.assertEqual(self.attempts(), 2)

    async def test_global_concurrency_across_two_instances(self):
        results = await asyncio.gather(
            self.state.reserve("104"), self.new_state().reserve("105"),
            return_exceptions=True,
        )
        self.assertEqual(sum(item is True for item in results), 1)
        errors = [item for item in results if isinstance(item, UserError)]
        self.assertEqual(len(errors), 1)
        self.assertEqual(str(errors[0]), BUSY_ERROR)
        self.assertEqual(self.attempts(), 1)

    async def test_parallel_duplicate_reserves_only_once(self):
        results = await asyncio.gather(
            self.state.reserve("106"), self.new_state().reserve("106")
        )
        self.assertCountEqual(results, [True, False])
        self.assertEqual(self.attempts(), 1)

    async def test_limit_includes_failed_model_request(self):
        # finish is called for both provider success and failure, without refund.
        for interaction_id in ("107", "108"):
            self.assertTrue(await self.state.reserve(interaction_id))
            await self.state.finish(interaction_id)
            self.clock.advance(10)
        with self.assertRaisesRegex(UserError, LIMIT_ERROR):
            await self.state.reserve("109")
        self.assertEqual(self.attempts(), 2)

    async def test_cooldown_survives_container_restart(self):
        await self.state.reserve("110")
        await self.state.finish("110")
        self.clock.advance(9)
        with self.assertRaisesRegex(UserError, "10초"):
            await self.new_state().reserve("111")
        self.assertEqual(self.attempts(), 1)
        self.clock.advance(1)
        self.assertTrue(await self.new_state().reserve("111"))

    async def test_korean_midnight_resets_counter_but_preserves_global_lease(self):
        self.clock.now = datetime(2026, 10, 27, 14, 59, 59, tzinfo=timezone.utc).timestamp()
        await self.state.reserve("112")
        self.clock.advance(2)
        with self.assertRaisesRegex(UserError, BUSY_ERROR):
            await self.state.reserve("113")
        self.assertEqual(self.attempts("2026-10-28"), 0)
        await self.state.finish("112")
        self.clock.advance(10)
        self.assertTrue(await self.state.reserve("113"))
        self.assertEqual(self.attempts("2026-10-27"), 1)
        self.assertEqual(self.attempts("2026-10-28"), 1)
        self.assertFalse(await self.state.reserve("112"))

    async def test_late_completion_cannot_unlock_new_owner(self):
        await self.state.reserve("114")
        self.clock.advance(301)
        await self.new_state().reserve("115")
        await self.state.finish("114")
        with self.assertRaisesRegex(UserError, BUSY_ERROR):
            await self.new_state().reserve("116")
        await self.state.finish("115")
        self.assertEqual(self.backend.documents["global"]["busy_until"], 0)

    async def test_datastore_failure_is_safe_and_does_not_consume_partial_count(self):
        self.backend.fail_before_commit = True
        with self.assertRaisesRegex(UserError, STATE_ERROR) as caught:
            await self.state.reserve("117")
        self.assertNotIn("private", str(caught.exception))
        self.assertEqual(self.backend.documents, {})

    async def test_ambiguous_commit_prevents_duplicate_generation(self):
        self.backend.fail_after_commit = True
        with self.assertRaises(UserError):
            await self.state.reserve("118")
        self.backend.fail_after_commit = False
        self.clock.advance(301)
        self.assertFalse(await self.state.reserve("118"))
        self.assertEqual(self.attempts(), 1)

    async def test_finish_failure_keeps_lease_for_safe_recovery(self):
        await self.state.reserve("119")
        self.backend.fail_before_commit = True
        with self.assertRaises(UserError):
            await self.state.finish("119")
        self.backend.fail_before_commit = False
        self.clock.advance(20)
        with self.assertRaisesRegex(UserError, BUSY_ERROR):
            await self.state.reserve("120")
        self.clock.advance(281)
        self.assertTrue(await self.state.reserve("120"))

    async def test_finished_or_unknown_finish_is_idempotent(self):
        await self.state.finish("121")
        self.assertEqual(self.backend.documents, {})
        await self.state.reserve("121")
        await self.state.finish("121")
        prior = deepcopy(self.backend.documents)
        await self.state.finish("121")
        self.assertEqual(self.backend.documents, prior)

    async def test_only_content_free_metadata_is_written(self):
        interaction_id = "1564099441110286398"
        await self.state.reserve(interaction_id)
        await self.state.finish(interaction_id)
        serialized = json.dumps(self.backend.documents)
        self.assertNotIn(interaction_id, serialized)
        self.assertNotIn("user_id", serialized)
        self.assertNotIn("text", serialized)
        self.assertNotIn("token", serialized)
        self.assertEqual(self.attempts(), 1)

    async def test_corrupted_counter_fails_closed(self):
        self.backend.documents["day_2026-10-27"] = {"attempts": "0"}
        with self.assertRaisesRegex(UserError, STATE_ERROR):
            await self.state.reserve("122")
        self.assertEqual(len(self.backend.documents), 1)

    async def test_invalid_request_id_never_accesses_store(self):
        for value in ("", "0", "../other", "a" * 100, str(1 << 64), 123):
            with self.subTest(value=value):
                with self.assertRaises(UserError):
                    await self.state.reserve(value)
        self.assertEqual(self.backend.documents, {})

    def test_lease_must_cover_provider_timeout(self):
        with self.assertRaises(ValueError):
            CloudState(replace(self.settings, timeout_seconds=290), backend=self.backend)


if __name__ == "__main__":
    unittest.main()
