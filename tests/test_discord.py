"""Offline adapter checks: every Discord HTTP call is forbidden."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from nuri.config import Settings
from nuri.discord_app import (
    MAX_RESPONSE_PAGES,
    NuriClient,
    _PracticeModal,
    _PracticeView,
    _send_error,
    _split_text,
    build_embeds,
    run_bot,
)
from nuri.models import Expression, Result, UserError


def interaction(user_id=123, done=False):
    response = SimpleNamespace(
        is_done=MagicMock(return_value=done),
        send_message=AsyncMock(),
        send_modal=AsyncMock(),
    )

    async def defer(**kwargs):
        response.is_done.return_value = True

    response.defer = AsyncMock(side_effect=defer)
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=response,
        edit_original_response=AsyncMock(),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


class EmbedTests(unittest.TestCase):
    def test_mixed_unicode_chunks_reassemble_exactly(self):
        original = ("A한글🦊😀e\u0301\n" * 1200) + "끝"
        chunks = _split_text(original)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), original)
        self.assertTrue(all(utf16_length(x) <= 4000 for x in chunks))

    def test_embed_pages_preserve_long_text_within_budget(self):
        text = "abc🦊\n" * 2100
        pages = build_embeds([("긴 원문", text)])
        self.assertEqual("".join(page.description for page in pages), text)
        self.assertTrue(all(utf16_length(p.description) <= 4096 for p in pages))
        self.assertTrue(all(utf16_length(p.title) <= 256 for p in pages))
        self.assertTrue(
            all(utf16_length(p.title + p.description + p.footer.text) <= 6000 for p in pages)
        )

    def test_long_result_is_explicitly_truncated_at_followup_budget(self):
        pages = build_embeds([("제목", "a" * 4000 * (MAX_RESPONSE_PAGES + 1))])
        self.assertEqual(len(pages), 6)
        self.assertIn("일부 생략", pages[-1].footer.text)
        self.assertEqual("".join(p.description for p in pages), "a" * 24000)

    def test_exact_six_pages_are_not_reported_as_truncated(self):
        pages = build_embeds([("제목", "a" * 24000)])
        self.assertEqual(len(pages), 6)
        self.assertNotIn("생략", pages[-1].footer.text)

    def test_empty_result_still_has_a_valid_embed(self):
        pages = build_embeds([("빈 항목", "")])
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].description)


class DiscordAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.http_guard = patch(
            "discord.http.HTTPClient.request",
            new=AsyncMock(side_effect=AssertionError("Live Discord HTTP is forbidden in tests.")),
        )
        self.http_guard.start()
        self.addCleanup(self.http_guard.stop)
        self.settings = Settings(allowed_user_ids=frozenset((456,)))
        self.service = SimpleNamespace(run=AsyncMock())
        self.client = NuriClient(self.settings, self.service)
        # Initialize the library's loop bookkeeping without logging in.
        await self.client._async_setup_hook()
        self.addAsyncCleanup(self.client.close)

    def test_serialized_commands_use_user_install_and_no_intents(self):
        self.assertEqual(self.client.intents.value, 0)
        payloads = [command.to_dict(self.client.tree) for command in self.client.tree.get_commands()]
        by_name = {payload["name"]: payload for payload in payloads}
        self.assertEqual(set(by_name), {"nuri", "Nuri 번역", "Nuri와 영어 배우기"})
        for payload in payloads:
            self.assertEqual(payload["contexts"], [0, 1, 2])
            self.assertEqual(payload["integration_types"], [1])
            self.assertIsNone(payload["default_member_permissions"])
        self.assertEqual(by_name["Nuri 번역"]["type"], 3)
        self.assertEqual(by_name["Nuri와 영어 배우기"]["type"], 3)
        choices = by_name["nuri"]["options"][1]["choices"]
        self.assertEqual({choice["value"] for choice in choices}, {"translate", "learn"})

    async def test_allowlist_is_empty_until_application_owner_is_resolved(self):
        self.assertEqual(self.client.allowed_user_ids, frozenset())
        call = interaction(456)
        self.assertFalse(await self.client.authorize(call))
        call.response.send_message.assert_awaited_once()
        self.assertTrue(call.response.send_message.await_args.kwargs["ephemeral"])

    async def test_app_owner_and_explicit_allowlist_are_unioned(self):
        self.client.application_info = AsyncMock(
            return_value=SimpleNamespace(
                id=self.settings.expected_application_id, team=None, owner=SimpleNamespace(id=123)
            )
        )
        await self.client.setup_hook()
        self.assertEqual(self.client.allowed_user_ids, frozenset((123, 456)))
        self.assertTrue(await self.client.authorize(interaction(123)))
        self.assertTrue(await self.client.authorize(interaction(456)))
        other = interaction(999)
        other.user.guild_permissions = SimpleNamespace(administrator=True)
        self.assertFalse(await self.client.authorize(other))

    async def test_team_owner_is_used_instead_of_app_pseudo_owner(self):
        self.client.application_info = AsyncMock(
            return_value=SimpleNamespace(
                id=self.settings.expected_application_id,
                team=SimpleNamespace(owner_id=789), owner=SimpleNamespace(id=123)
            )
        )
        await self.client.setup_hook()
        self.assertEqual(self.client.allowed_user_ids, frozenset((789, 456)))

    async def test_owner_lookup_failure_is_closed_and_does_not_expose_error(self):
        self.client.application_info = AsyncMock(side_effect=RuntimeError("SECRET_TOKEN"))
        with self.assertRaises(UserError) as caught:
            await self.client.setup_hook()
        self.assertNotIn("SECRET_TOKEN", str(caught.exception))
        self.assertEqual(self.client.allowed_user_ids, frozenset())

    async def test_invalid_owner_is_rejected(self):
        self.client.application_info = AsyncMock(
            return_value=SimpleNamespace(
                id=self.settings.expected_application_id, team=None, owner=SimpleNamespace(id=None)
            )
        )
        with self.assertRaises(UserError):
            await self.client.setup_hook()
        self.assertEqual(self.client.allowed_user_ids, frozenset())

    async def test_wrong_or_missing_application_id_is_rejected_and_clears_allowlist(self):
        for application_id in (1496543182958362704, None, str(self.settings.expected_application_id)):
            with self.subTest(application_id=application_id):
                self.client.allowed_user_ids = frozenset((123, 456))
                self.client.application_info = AsyncMock(return_value=SimpleNamespace(
                    id=application_id, team=None, owner=SimpleNamespace(id=123)
                ))
                with self.assertRaisesRegex(UserError, "Nuri 번역 전용 앱의 토큰"):
                    await self.client.setup_hook()
                self.assertEqual(self.client.allowed_user_ids, frozenset())

    async def test_register_never_syncs_commands_for_another_application(self):
        self.client.application_info = AsyncMock(return_value=SimpleNamespace(
            id=1496543182958362704, team=None, owner=SimpleNamespace(id=123)
        ))

        async def login_with_setup_hook(token):
            await self.client.setup_hook()

        self.client.login = AsyncMock(side_effect=login_with_setup_hook)
        self.client.tree.sync = AsyncMock()
        with patch("nuri.discord_app.NuriClient", return_value=self.client):
            with self.assertRaisesRegex(UserError, "Nuri 번역 전용 앱의 토큰"):
                await run_bot(Settings(discord_token="offline-test-value"), self.service, register=True)
        self.client.tree.sync.assert_not_awaited()

    async def test_unauthorized_request_never_reaches_provider(self):
        call = interaction(999)
        await self.client.execute(call, "A sentence", "learn")
        self.service.run.assert_not_awaited()
        call.response.defer.assert_not_awaited()
        self.assertTrue(call.response.send_message.await_args.kwargs["ephemeral"])

    async def test_attachment_only_message_is_rejected_without_provider(self):
        self.client.allowed_user_ids = frozenset((123,))
        call = interaction()
        await self.client.translate_message(call, SimpleNamespace(content=""))
        self.service.run.assert_not_awaited()
        self.assertTrue(call.response.send_message.await_args.kwargs["ephemeral"])

    async def test_selected_role_ping_reads_embed_body_before_service(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.return_value = Result("The release is ready.", "learn", "출시 준비가 됐어요.")
        call = interaction()
        message = SimpleNamespace(content="<@&1224161131703042068>", embeds=[
            discord.Embed(description="The release is ready.")])
        await self.client.learn_message(call, message)
        self.service.run.assert_awaited_once_with(123, "The release is ready.", "learn")
        self.addCleanup(call.edit_original_response.await_args.kwargs["view"].stop)

    async def test_selected_mentions_only_rejected_before_service(self):
        self.client.allowed_user_ids = frozenset((123,))
        call = interaction()
        await self.client.learn_message(call, SimpleNamespace(content="<@&1224161131703042068>", embeds=[]))
        self.service.run.assert_not_awaited()
        call.response.defer.assert_not_awaited()
        self.assertIn("멘션만", call.response.send_message.await_args.args[0])
        self.assertTrue(call.response.send_message.await_args.kwargs["ephemeral"])

    async def test_selected_combined_embed_limit_rejected_before_service(self):
        self.client.allowed_user_ids = frozenset((123,))
        call = interaction()
        message = SimpleNamespace(content="x" * 1500, embeds=[discord.Embed(description="y" * 1500)])
        await self.client.translate_message(call, message)
        self.service.run.assert_not_awaited()
        call.response.defer.assert_not_awaited()
        self.assertIn("3,000", call.response.send_message.await_args.args[0])

    async def test_translation_defers_privately_and_never_posts_to_channel(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.return_value = Result(
            source="We rolled out the update.", mode="translate", translation="업데이트를 배포했습니다."
        )
        call = interaction()
        await self.client.execute(call, "We rolled out the update.", "translate")
        call.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        self.service.run.assert_awaited_once_with(123, "We rolled out the update.", "translate")
        self.assertIsNone(call.edit_original_response.await_args.kwargs["view"])
        first = call.edit_original_response.await_args.kwargs
        self.assertTrue(first["content"].startswith("**번역**\n업데이트를 배포했습니다."))
        self.assertIn("**원문**\nWe rolled out the update.", first["content"])
        self.assertEqual(first["embeds"], [])
        call.followup.send.assert_not_awaited()
        for followup in call.followup.send.await_args_list:
            self.assertTrue(followup.kwargs["ephemeral"])
            self.assertEqual(followup.kwargs["allowed_mentions"].to_dict()["parse"], [])

    async def test_learning_adds_owner_bound_practice_button(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.return_value = Result(
            source="We rolled out the update.",
            mode="learn",
            translation="업데이트를 배포했습니다.",
            expressions=(Expression("roll out", "출시하다"),),
        )
        call = interaction()
        await self.client.execute(call, "We rolled out the update.", "learn")
        view = call.edit_original_response.await_args.kwargs["view"]
        self.addCleanup(view.stop)
        self.assertIsInstance(view, _PracticeView)
        self.assertEqual(view.owner_id, 123)
        self.assertEqual(view.timeout, 600)
        self.assertIn("roll out — 출시하다", call.edit_original_response.await_args.kwargs["content"])
        self.assertEqual(call.edit_original_response.await_args.kwargs["embeds"], [])

    async def test_long_plain_results_keep_followups_private_and_within_limits(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.return_value = Result("Original", "translate", translation="긴 번역🦊" * 2000)
        call = interaction()
        await self.client.execute(call, "Original", "translate")
        followups = call.followup.send.await_args_list
        self.assertGreater(len(followups), 0)
        self.assertLessEqual(len(followups), 5)
        for sent in [call.edit_original_response.await_args, *followups]:
            self.assertLessEqual(utf16_length(sent.kwargs["content"]), 2000)
            self.assertEqual(sent.kwargs["embeds"], [])
            self.assertEqual(sent.kwargs["allowed_mentions"].to_dict()["parse"], [])
        for sent in followups:
            self.assertTrue(sent.kwargs["ephemeral"])
            self.assertTrue(sent.kwargs["suppress_embeds"])

    async def test_public_safe_service_error_is_private(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.side_effect = UserError("오늘의 요청 한도입니다.")
        call = interaction()
        await self.client.execute(call, "test", "learn")
        self.assertEqual(call.edit_original_response.await_args.kwargs["content"], "오늘의 요청 한도입니다.")
        call.followup.send.assert_not_awaited()

    async def test_unexpected_provider_error_does_not_leak_details(self):
        self.client.allowed_user_ids = frozenset((123,))
        self.service.run.side_effect = RuntimeError("SECRET_TOKEN PRIVATE_ORIGINAL")
        call = interaction()
        with patch("nuri.discord_app.LOGGER.warning") as warning:
            await self.client.execute(call, "PRIVATE_ORIGINAL", "learn")
        output = str(call.edit_original_response.await_args)
        self.assertNotIn("SECRET_TOKEN", output)
        self.assertNotIn("PRIVATE_ORIGINAL", output)
        self.assertNotIn("SECRET_TOKEN", str(warning.call_args_list))

    async def test_error_helper_never_falls_back_to_channel_message(self):
        call = interaction()
        call.channel = SimpleNamespace(send=AsyncMock())
        call.response.send_message.side_effect = discord.DiscordException("private failure")
        with patch("nuri.discord_app.LOGGER.warning"):
            await _send_error(call, "실패했습니다.")
        call.channel.send.assert_not_awaited()
        call.followup.send.assert_not_awaited()

    async def test_practice_view_rejects_wrong_user_and_expiration(self):
        self.client.allowed_user_ids = frozenset((123, 456))
        view = _PracticeView(self.client, 123)
        self.addCleanup(view.stop)
        wrong = interaction(456)
        self.assertFalse(await view.interaction_check(wrong))
        self.assertTrue(wrong.response.send_message.await_args.kwargs["ephemeral"])
        expired = interaction()
        with patch("nuri.discord_app.time.monotonic", return_value=view.expires_at + 1):
            self.assertFalse(await view.interaction_check(expired))
        expired.response.send_modal.assert_not_awaited()

    async def test_practice_button_opens_modal_without_defer(self):
        self.client.allowed_user_ids = frozenset((123,))
        view = _PracticeView(self.client, 123)
        self.addCleanup(view.stop)
        call = interaction()
        await view.practice.callback(call)
        call.response.defer.assert_not_awaited()
        modal = call.response.send_modal.await_args.args[0]
        self.addCleanup(modal.stop)
        self.assertEqual(modal.owner_id, 123)
        self.assertEqual(modal.expires_at, view.expires_at)
        self.assertEqual(modal.answer.max_length, 1000)

    async def test_practice_modal_rejects_wrong_user_and_expiration(self):
        self.client.allowed_user_ids = frozenset((123, 456))
        view = _PracticeView(self.client, 123)
        self.addCleanup(view.stop)
        modal = _PracticeModal(self.client, 123, view.expires_at)
        self.addCleanup(modal.stop)
        await modal.on_submit(interaction(456))
        with patch("nuri.discord_app.time.monotonic", return_value=view.expires_at + 1):
            await modal.on_submit(interaction(123))
        self.service.run.assert_not_awaited()

    async def test_run_does_not_sync_and_register_does_not_connect(self):
        for register in (False, True):
            with self.subTest(register=register):
                stub = MagicMock()
                stub.__aenter__ = AsyncMock(return_value=stub)
                stub.__aexit__ = AsyncMock(return_value=False)
                stub.login = AsyncMock()
                stub.connect = AsyncMock()
                stub.tree.sync = AsyncMock()
                with patch("nuri.discord_app.NuriClient", return_value=stub), patch("builtins.print"):
                    await run_bot(Settings(discord_token="offline-test-value"), self.service, register=register)
                if register:
                    stub.tree.sync.assert_awaited_once_with()
                    stub.connect.assert_not_awaited()
                else:
                    stub.tree.sync.assert_not_awaited()
                    stub.connect.assert_awaited_once_with(reconnect=True)


if __name__ == "__main__":
    unittest.main()
