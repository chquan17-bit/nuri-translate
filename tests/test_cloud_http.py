import base64
from dataclasses import replace
import hashlib
import io
import json
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer
from nacl.signing import SigningKey

from nuri.cloud_http import (
    APPLICATION_ID, CloudConfig, DiscordSender, EPHEMERAL, GENERIC_ERROR, SUPPRESS_EMBEDS,
    _component_id, create_app,
)
from nuri.cloud_queue import CloudTasksQueue, QUEUE_ERROR
from nuri.config import Settings
from nuri.models import Expression, Result, UserError


OWNER = 111111111111111111
OTHER = 222222222222222222
INTERACTION = "333333333333333333"
NOW = 1800000000
SECRET = "test-component-secret-never-a-real-secret"


class FakeQueue:
    def __init__(self):
        self.calls = []
        self.result = True
        self.error = None

    async def enqueue(self, payload):
        if self.error:
            raise self.error
        self.calls.append(payload)
        return self.result


class FakeState:
    def __init__(self):
        self.reservations = []
        self.finishes = []
        self.result = True
        self.error = None

    async def reserve(self, interaction_id):
        if self.error:
            raise self.error
        self.reservations.append(interaction_id)
        return self.result

    async def finish(self, interaction_id):
        self.finishes.append(interaction_id)


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.error = None

    async def generate(self, text, mode):
        self.calls.append((text, mode))
        if self.error:
            raise self.error
        return Result(source=text, mode=mode, translation="테스트 번역")


class FakeSender:
    def __init__(self):
        self.results = []
        self.errors = []

    async def result(self, task, result):
        self.results.append(result)

    async def error(self, task, message):
        self.errors.append(message)


class HTTPBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.signing = SigningKey.generate()
        self.config = CloudConfig("ingress", OWNER, self.signing.verify_key.encode().hex(), SECRET)
        self.settings = Settings(gemini_key="unit-test-key", api_enabled=True)
        self.queue = FakeQueue()
        self.clients = []
        self.client = await self.new_client(create_app(
            self.config, self.settings, queue=self.queue, clock=lambda: NOW))

    async def new_client(self, app):
        client = TestClient(TestServer(app))
        await client.start_server()
        self.clients.append(client)
        return client

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()

    def payload(self, **updates):
        payload = {
            "type": 2, "application_id": str(APPLICATION_ID), "id": INTERACTION,
            "user": {"id": str(OWNER)}, "token": "test-interaction-token",
            "data": {"type": 1, "name": "nuri", "options": [{"name": "text", "value": "Hello."}]},
        }
        payload.update(updates)
        return payload

    async def post(self, payload, *, stamp=NOW, tamper=False):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        signature = self.signing.sign(str(stamp).encode() + raw).signature.hex()
        if tamper:
            raw += b" "
        return await self.client.post("/interactions", data=raw, headers={
            "Content-Type": "application/json", "X-Signature-Timestamp": str(stamp),
            "X-Signature-Ed25519": signature,
        })

    async def test_real_ed25519_ping(self):
        response = await self.post({"type": 1, "application_id": str(APPLICATION_ID)})
        self.assertEqual(await response.json(), {"type": 1})
        self.assertEqual(self.queue.calls, [])

    async def test_signature_tamper_rejected_before_queue(self):
        response = await self.post(self.payload(), tamper=True)
        self.assertEqual(response.status, 401)
        self.assertEqual(self.queue.calls, [])

    async def test_missing_signature_rejected(self):
        response = await self.client.post("/interactions", json=self.payload())
        self.assertEqual(response.status, 401)

    async def test_old_and_future_timestamp_rejected(self):
        for stamp in (NOW - 301, NOW + 301):
            response = await self.post(self.payload(), stamp=stamp)
            self.assertEqual(response.status, 401)

    async def test_wrong_application_rejected(self):
        response = await self.post(self.payload(application_id=str(OTHER)))
        self.assertEqual(response.status, 401)
        self.assertEqual(self.queue.calls, [])

    async def test_non_owner_is_private_and_never_queued(self):
        response = await self.post(self.payload(user={"id": str(OTHER)}))
        data = await response.json()
        self.assertEqual(data["type"], 4)
        self.assertEqual(data["data"]["flags"], EPHEMERAL)
        self.assertEqual(data["data"]["allowed_mentions"], {"parse": []})
        self.assertEqual(self.queue.calls, [])

    async def test_slash_default_learn_deferred_private(self):
        response = await self.post(self.payload())
        self.assertEqual(await response.json(), {"type": 5, "data": {"flags": EPHEMERAL}})
        task = self.queue.calls[0]
        self.assertEqual((task["mode"], task["text"]), ("learn", "Hello."))
        self.assertEqual(task["interaction_id"], INTERACTION)
        self.assertEqual(task["created_at"], NOW)

    async def test_guild_owner_and_context_menu_selected_message_only(self):
        payload = self.payload(user=None, member={"user": {"id": str(OWNER)}})
        payload["data"] = {"type": 3, "name": "Nuri 번역", "target_id": "444444444444444444", "resolved": {
            "messages": {"444444444444444444": {"content": "Selected text"},
                         "555555555555555555": {"content": "Unselected private text"}}}}
        response = await self.post(payload)
        self.assertEqual((await response.json())["type"], 5)
        self.assertEqual(self.queue.calls[0]["text"], "Selected text")
        self.assertEqual(self.queue.calls[0]["mode"], "translate")
        self.assertNotIn("Unselected", json.dumps(self.queue.calls))

    async def test_input_limit_before_queue(self):
        payload = self.payload()
        payload["data"]["options"][0]["value"] = "x" * 3001
        response = await self.post(payload)
        self.assertEqual((await response.json())["type"], 4)
        self.assertEqual(self.queue.calls, [])

    async def test_context_menu_role_ping_and_embeds_supply_actual_body(self):
        payload = self.payload()
        payload["data"] = {"type": 3, "name": "Nuri와 영어 배우기", "target_id": "444444444444444444",
                           "resolved": {"messages": {"444444444444444444": {
                               "content": "<@&1224161131703042068>",
                               "embeds": [{"title": "Update", "description": "The release is ready.",
                                           "fields": [{"name": "Details", "value": "Try it today."}]}]}}}}
        response = await self.post(payload)
        self.assertEqual((await response.json())["type"], 5)
        self.assertEqual(self.queue.calls[0]["text"], "Update\n\nThe release is ready.\n\nDetails\n\nTry it today.")
        self.assertEqual(self.queue.calls[0]["mode"], "learn")

    async def test_context_menu_mentions_only_rejected_before_queue(self):
        payload = self.payload()
        payload["data"] = {"type": 3, "name": "Nuri 번역", "target_id": "444444444444444444",
                           "resolved": {"messages": {"444444444444444444": {
                               "content": "<@&1224161131703042068>"}}}}
        response = await self.post(payload)
        body = await response.json()
        self.assertEqual(body["type"], 4)
        self.assertEqual(body["data"]["flags"], EPHEMERAL)
        self.assertIn("멘션만", body["data"]["content"])
        self.assertEqual(self.queue.calls, [])

    async def test_context_menu_combined_embed_limit_rejected_before_queue(self):
        payload = self.payload()
        payload["data"] = {"type": 3, "name": "Nuri 번역", "target_id": "444444444444444444",
                           "resolved": {"messages": {"444444444444444444": {
                               "content": "x" * 1500, "embeds": [{"description": "y" * 1500}]}}}}
        response = await self.post(payload)
        body = await response.json()
        self.assertEqual(body["type"], 4)
        self.assertIn("3,000", body["data"]["content"])
        self.assertEqual(self.queue.calls, [])

    async def test_slash_cannot_bypass_practice_button(self):
        payload = self.payload()
        payload["data"]["options"].append({"name": "mode", "value": "practice"})
        response = await self.post(payload)
        self.assertEqual((await response.json())["type"], 4)
        self.assertEqual(self.queue.calls, [])

    async def test_signed_practice_button_opens_bound_modal_without_queue(self):
        custom_id = _component_id("p", OWNER, NOW + 600, SECRET)
        response = await self.post(self.payload(type=3, data={"custom_id": custom_id}))
        data = await response.json()
        self.assertEqual(data["type"], 9)
        self.assertEqual(data["data"]["custom_id"], _component_id("m", OWNER, NOW + 600, SECRET))
        self.assertEqual(data["data"]["components"][0]["components"][0]["max_length"], 1000)
        self.assertEqual(self.queue.calls, [])

    async def test_practice_rejects_expired_wrong_owner_and_forgery(self):
        for value in (_component_id("p", OWNER, NOW, SECRET),
                      _component_id("p", OTHER, NOW + 500, SECRET),
                      _component_id("p", OWNER, NOW + 500, SECRET + "wrong")):
            response = await self.post(self.payload(type=3, data={"custom_id": value}))
            self.assertEqual((await response.json())["type"], 4)
        self.assertEqual(self.queue.calls, [])

    async def test_modal_submit_keeps_owner_expiry_and_practice_limit(self):
        data = {"custom_id": _component_id("m", OWNER, NOW + 300, SECRET),
                "components": [{"type": 1, "components": [{"type": 4,
                    "custom_id": "nuri_sentence", "value": "I learn English."}]}]}
        response = await self.post(self.payload(type=5, data=data))
        self.assertEqual((await response.json())["type"], 5)
        self.assertEqual(self.queue.calls[0]["mode"], "practice")
        data["components"][0]["components"][0]["value"] = "x" * 1001
        response = await self.post(self.payload(type=5, data=data))
        self.assertEqual((await response.json())["type"], 4)
        self.assertEqual(len(self.queue.calls), 1)

    async def test_duplicate_task_still_acknowledges_private(self):
        self.queue.result = False
        response = await self.post(self.payload())
        self.assertEqual(await response.json(), {"type": 5, "data": {"flags": 64}})

    async def test_queue_failure_does_not_send_public_response(self):
        self.queue.error = UserError(QUEUE_ERROR)
        response = await self.post(self.payload())
        data = await response.json()
        self.assertEqual(data["type"], 4)
        self.assertEqual(data["data"]["flags"], 64)
        self.assertEqual(data["data"]["content"], QUEUE_ERROR)

    async def test_ingress_has_no_task_route(self):
        response = await self.client.post("/tasks", json={})
        self.assertEqual(response.status, 404)

    async def worker_client(self):
        self.state = FakeState()
        self.provider = FakeProvider()
        self.sender = FakeSender()
        return await self.new_client(create_app(
            replace(self.config, role="worker"), self.settings,
            state=self.state, provider=self.provider, sender=self.sender, clock=lambda: NOW))

    def task(self, **updates):
        value = {"application_id": str(APPLICATION_ID), "user_id": str(OWNER),
                 "interaction_id": INTERACTION, "token": "test-interaction-token",
                 "created_at": NOW, "text": "Hello.", "mode": "learn"}
        value.update(updates)
        return value

    async def test_worker_has_no_interactions_route(self):
        client = await self.worker_client()
        response = await client.post("/interactions", json=self.payload())
        self.assertEqual(response.status, 404)

    async def test_worker_success_reserves_calls_provider_and_finishes(self):
        client = await self.worker_client()
        response = await client.post("/tasks", json=self.task())
        self.assertEqual(await response.json(), {"ok": True})
        self.assertEqual(self.state.reservations, [INTERACTION])
        self.assertEqual(self.state.finishes, [INTERACTION])
        self.assertEqual(self.provider.calls, [("Hello.", "learn")])
        self.assertEqual(len(self.sender.results), 1)

    async def test_worker_duplicate_never_generates_or_overwrites_response(self):
        client = await self.worker_client()
        self.state.result = False
        response = await client.post("/tasks", json=self.task())
        self.assertTrue((await response.json())["duplicate"])
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.sender.results, [])
        self.assertEqual(self.sender.errors, [])
        self.assertEqual(self.state.finishes, [])

    async def test_worker_rejects_cross_owner_or_expired_task(self):
        client = await self.worker_client()
        for task in (self.task(user_id=str(OTHER)), self.task(created_at=NOW - 601),
                     self.task(application_id=str(OTHER)), self.task(token="token/unsafe")):
            response = await client.post("/tasks", json=task)
            self.assertEqual(response.status, 400)
        self.assertEqual(self.state.reservations, [])
        self.assertEqual(self.provider.calls, [])

    async def test_worker_revalidates_input_before_quota(self):
        client = await self.worker_client()
        await client.post("/tasks", json=self.task(text="x" * 3001))
        self.assertEqual(self.state.reservations, [])
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(len(self.sender.errors), 1)

    async def test_worker_quota_fail_closed(self):
        client = await self.worker_client()
        self.state.error = UserError("오늘의 한도에 도달했습니다.")
        await client.post("/tasks", json=self.task())
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.sender.errors, ["오늘의 한도에 도달했습니다."])
        self.assertEqual(self.state.finishes, [])

    async def test_worker_does_not_log_or_return_provider_exception_or_text(self):
        client = await self.worker_client()
        self.provider.error = RuntimeError("DO-NOT-EXPOSE-request-secret")
        output = io.StringIO()
        with redirect_stdout(output):
            response = await client.post("/tasks", json=self.task(text="DO-NOT-EXPOSE-private-text"))
            response_text = await response.text()
        self.assertNotIn("DO-NOT-EXPOSE", output.getvalue() + response_text + str(self.sender.errors))
        self.assertEqual(self.sender.errors, [GENERIC_ERROR])
        self.assertEqual(self.state.finishes, [INTERACTION])

    async def test_real_sender_preserves_pages_mentions_and_ephemeral_followups(self):
        config = replace(self.config, role="worker")
        sender = DiscordSender(config, clock=lambda: NOW)
        sender._request = AsyncMock()
        result = Result("Hello.", "learn", translation="안녕하세요.",
                        expressions=(Expression("Hello", "안녕하세요"),))
        await sender.result(self.task(), result)
        calls = sender._request.await_args_list
        self.assertEqual(len(calls), 1)
        first = calls[0].args[3]
        self.assertTrue(first["content"].startswith("**번역**\n안녕하세요."))
        self.assertIn("**다시 쓸 표현**\nHello — 안녕하세요", first["content"])
        self.assertIn("**원문**\nHello.", first["content"])
        self.assertEqual(first["embeds"], [])
        self.assertEqual(first["flags"], SUPPRESS_EMBEDS)
        self.assertEqual(first["allowed_mentions"], {"parse": []})
        self.assertEqual(first["components"][0]["components"][0]["custom_id"],
                         _component_id("p", OWNER, NOW + 600, SECRET))
        sender._request.reset_mock()
        await sender.result(self.task(), Result("Hello.", "translate", translation="번역🦊" * 2000))
        calls = sender._request.await_args_list
        self.assertGreater(len(calls), 1)
        self.assertLessEqual(len(calls), 6)
        for call in calls:
            self.assertTrue(call.args[3]["content"])
            self.assertLessEqual(len(call.args[3]["content"].encode("utf-16-le")) // 2, 2000)
            self.assertEqual(call.args[3]["embeds"], [])
        for call in calls[1:]:
            self.assertEqual(call.args[3]["flags"], EPHEMERAL | SUPPRESS_EMBEDS)
            self.assertEqual(call.args[3]["allowed_mentions"], {"parse": []})


class FakeResponse:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeSession:
    closed = False

    def __init__(self, status):
        self.status = status
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.status)


class QueueBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def queue(self, status=200):
        queue = CloudTasksQueue("nuri-test", "asia-northeast3", "nuri-translation",
                                "https://worker-example.a.run.app",
                                "nuri-task@nuri-test.iam.gserviceaccount.com", clock=lambda: NOW)
        queue._token = AsyncMock(return_value="not-a-real-access-token")
        queue._session = FakeSession(status)
        return queue

    async def test_task_is_deterministic_delayed_private_oidc_and_no_retry(self):
        queue = self.queue()
        payload = {"interaction_id": INTERACTION, "text": "Private sentence", "token": "test-token"}
        self.assertTrue(await queue.enqueue(payload))
        request = queue._session.calls[0][1]
        task = request["json"]["task"]
        expected = "nuri-" + hashlib.sha256(INTERACTION.encode()).hexdigest()
        self.assertTrue(task["name"].endswith(expected))
        self.assertEqual(task["dispatchDeadline"], "270s")
        self.assertEqual(task["httpRequest"]["oidcToken"]["audience"], "https://worker-example.a.run.app")
        self.assertEqual(json.loads(base64.b64decode(task["httpRequest"]["body"])), payload)
        self.assertFalse(request["allow_redirects"])
        self.assertEqual(len(queue._session.calls), 1)

    async def test_already_exists_is_safe_duplicate(self):
        queue = self.queue(409)
        self.assertFalse(await queue.enqueue({"interaction_id": INTERACTION}))
        self.assertEqual(len(queue._session.calls), 1)

    async def test_google_error_is_safe_and_not_retried(self):
        queue = self.queue(403)
        with self.assertRaisesRegex(UserError, QUEUE_ERROR):
            await queue.enqueue({"interaction_id": INTERACTION})
        self.assertEqual(len(queue._session.calls), 1)

    async def test_auth_lock_contention_obeys_total_discord_ack_deadline(self):
        queue = CloudTasksQueue("nuri-test", "asia-northeast3", "nuri-translation",
                                "https://worker-example.a.run.app",
                                "nuri-task@nuri-test.iam.gserviceaccount.com")
        queue._session = FakeSession(200)
        # Another request still owns a slow credential refresh. The outer
        # deadline must include waiting for this lock, not only API time.
        await queue._auth_lock.acquire()
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(UserError, QUEUE_ERROR):
                await queue.enqueue({"interaction_id": INTERACTION})
            self.assertLess(time.monotonic() - started, 2.5)
            self.assertTrue(queue._auth_lock.locked())
            self.assertEqual(queue._session.calls, [])
        finally:
            queue._auth_lock.release()

    def test_queue_refuses_external_or_credential_bearing_worker_url(self):
        for url in ("https://evil.example", "https://user@worker.a.run.app", "http://worker.a.run.app",
                    "https://worker.a.run.app?secret=bad"):
            with self.assertRaises(ValueError):
                CloudTasksQueue("nuri-test", "asia-northeast3", "nuri-translation", url,
                                "nuri-task@nuri-test.iam.gserviceaccount.com")


if __name__ == "__main__":
    unittest.main()
