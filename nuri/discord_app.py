"""Private, on-demand Discord adapter for Nuri.

Only application commands are consumed; no message listener or privileged
gateway intent is enabled. Credentials and message bodies are never logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Literal

import discord
from discord import app_commands

from .config import Settings
from .render import MAX_RESPONSE_PAGES, build_text_pages, render_result
from .service import NuriService, UserError
from .selected_message import selected_message_text


LOGGER = logging.getLogger(__name__)
COBALT = 0x2456D8
PRACTICE_TTL = 600.0
NO_MENTIONS = discord.AllowedMentions.none()


def _split_text(text: str, limit: int = 4000) -> list[str]:
    """Split without dropping text or cutting a Unicode scalar in half."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for char in text:
        size = 2 if ord(char) > 0xFFFF else 1
        if length + size > limit and current:
            chunks.append("".join(current))
            current = []
            length = 0
        current.append(char)
        length += size
    if current:
        chunks.append("".join(current))
    return chunks


def build_embeds(sections: Iterable[tuple[str, str]]) -> list[discord.Embed]:
    """Keep every message below Discord's per-embed and aggregate limits."""
    pages: list[discord.Embed] = []
    truncated = False
    for title, body in sections:
        if not body:
            continue
        safe_title = _split_text(str(title), 220)[0] if title else "Nuri"
        for part_number, part in enumerate(_split_text(str(body)), start=1):
            if len(pages) >= MAX_RESPONSE_PAGES:
                truncated = True
                break
            suffix = f" · 계속 {part_number}" if part_number > 1 else ""
            pages.append(
                discord.Embed(title=safe_title + suffix, description=part, colour=COBALT)
            )
        if truncated:
            break

    if not pages:
        pages.append(
            discord.Embed(
                title="Nuri",
                description="표시할 결과가 없습니다. 문장을 바꿔 다시 시도해 주세요.",
                colour=COBALT,
            )
        )

    for index, page in enumerate(pages, start=1):
        footer = f"Nuri · 나에게만 표시 · {index}/{len(pages)}"
        if truncated and index == len(pages):
            footer += " · 긴 출력 일부 생략: 문장을 나누어 다시 요청해 주세요."
        page.set_footer(text=footer)
    return pages


async def _send_error(interaction: discord.Interaction, message: str) -> None:
    """Best-effort private errors; never fall back to a channel message."""
    public_message = _split_text(message, 1800)[0] if message else "처리하지 못했습니다."
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(
                content=public_message, embeds=[], view=None, allowed_mentions=NO_MENTIONS
            )
        else:
            await interaction.response.send_message(
                public_message, ephemeral=True, allowed_mentions=NO_MENTIONS
            )
    except discord.DiscordException:
        LOGGER.warning("A private Discord error response could not be delivered.")


class _NuriTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.client.authorize(interaction)

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        # The library's default handler logs tracebacks, which can include input.
        LOGGER.warning("An application command failed.")
        await _send_error(interaction, "명령을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.")


class _PracticeModal(discord.ui.Modal):
    def __init__(self, client: NuriClient, owner_id: int, expires_at: float) -> None:
        super().__init__(
            title="Nuri와 한 문장 써보기",
            timeout=max(0.1, expires_at - time.monotonic()),
        )
        self.client = client
        self.owner_id = owner_id
        self.expires_at = expires_at
        self.answer = discord.ui.TextInput(
            label="내 영어 문장",
            placeholder="배운 표현으로 영어 한 문장을 써 보세요.",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=max(1, min(1000, client.settings.max_input_chars)),
        )
        self.add_item(self.answer)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await _send_error(interaction, "이 연습은 요청한 사람만 사용할 수 있습니다.")
            return False
        if time.monotonic() >= self.expires_at:
            await _send_error(interaction, "연습 시간이 끝났습니다. Nuri를 다시 실행해 주세요.")
            return False
        return await self.client.authorize(interaction)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Check again so a direct callback cannot bypass the owner/time boundary.
        if await self.interaction_check(interaction):
            await self.client.execute(interaction, str(self.answer.value), "practice")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        LOGGER.warning("A private practice modal failed.")
        await _send_error(interaction, "연습 문장을 처리하지 못했습니다. 다시 시도해 주세요.")


class _PracticeView(discord.ui.View):
    def __init__(self, client: NuriClient, owner_id: int) -> None:
        super().__init__(timeout=PRACTICE_TTL)
        self.client = client
        self.owner_id = owner_id
        self.expires_at = time.monotonic() + PRACTICE_TTL

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await _send_error(interaction, "이 버튼은 요청한 사람만 사용할 수 있습니다.")
            return False
        if time.monotonic() >= self.expires_at:
            await _send_error(interaction, "버튼 사용 시간이 끝났습니다. Nuri를 다시 실행해 주세요.")
            return False
        return await self.client.authorize(interaction)

    @discord.ui.button(label="한 문장 써보기", style=discord.ButtonStyle.primary)
    async def practice(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if await self.interaction_check(interaction):
            # Opening a modal must be the initial response: do not defer here.
            await interaction.response.send_modal(
                _PracticeModal(self.client, self.owner_id, self.expires_at)
            )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        LOGGER.warning("A private practice button failed.")
        await _send_error(interaction, "연습 창을 열지 못했습니다. Nuri를 다시 실행해 주세요.")


class NuriClient(discord.Client):
    def __init__(self, settings: Settings, service: NuriService) -> None:
        super().__init__(intents=discord.Intents.none(), allowed_mentions=NO_MENTIONS)
        self.settings = settings
        self.service = service
        # Empty until the application's owner has been verified through Discord.
        self.allowed_user_ids: frozenset[int] = frozenset()
        self.tree = _NuriTree(
            self,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=app_commands.AppInstallationType(guild=False, user=True),
        )
        self.tree.add_command(
            app_commands.ContextMenu(name="Nuri 번역", callback=self.translate_message)
        )
        self.tree.add_command(
            app_commands.ContextMenu(name="Nuri와 영어 배우기", callback=self.learn_message)
        )
        self.tree.add_command(
            app_commands.Command(
                name="nuri",
                description="나에게만 표시되는 Nuri 번역과 영어 학습",
                callback=self.slash_nuri,
            )
        )

    async def setup_hook(self) -> None:
        self.allowed_user_ids = frozenset()
        try:
            info = await self.application_info()
        except Exception:
            raise UserError("Discord 앱 소유자를 확인하지 못해 실행을 중단했습니다.") from None
        if getattr(info, "id", None) != self.settings.expected_application_id:
            raise UserError("Nuri 번역 전용 앱의 토큰이 아닙니다. 새 Nuri 앱의 Bot Token을 확인해 주세요.")
        try:
            owner_id = info.team.owner_id if info.team is not None else info.owner.id
        except Exception:
            raise UserError("Discord 앱 소유자를 확인하지 못해 실행을 중단했습니다.") from None
        if not isinstance(owner_id, int) or owner_id <= 0:
            raise UserError("Discord 앱 소유자를 확인하지 못해 실행을 중단했습니다.")
        self.allowed_user_ids = self.settings.allowed_user_ids | frozenset((owner_id,))

    async def authorize(self, interaction: discord.Interaction) -> bool:
        # Guild administrator status intentionally grants no access.
        if interaction.user.id in self.allowed_user_ids:
            return True
        await _send_error(interaction, "현재 Nuri는 소유자와 등록된 사용자만 사용할 수 있습니다.")
        return False

    async def translate_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.execute_selected_message(interaction, message, "translate")

    async def learn_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.execute_selected_message(interaction, message, "learn")

    async def execute_selected_message(
        self, interaction: discord.Interaction, message: discord.Message, mode: str
    ) -> None:
        if not await self.authorize(interaction):
            return
        try:
            text = selected_message_text({
                "content": message.content,
                "embeds": [embed.to_dict() for embed in getattr(message, "embeds", [])],
            })
            if len(text) > self.settings.max_input_chars:
                raise UserError(f"한 번에 {self.settings.max_input_chars:,}자까지 사용할 수 있어요. 문단을 나눠 주세요.")
        except UserError as error:
            await _send_error(interaction, str(error))
            return
        await self.execute(interaction, text, mode)

    @app_commands.describe(text="번역하거나 배울 문장", mode="learn: 영어 학습 / translate: 번역")
    async def slash_nuri(
        self,
        interaction: discord.Interaction,
        text: str,
        mode: Literal["translate", "learn"] = "learn",
    ) -> None:
        await self.execute(interaction, text, mode)

    async def execute(self, interaction: discord.Interaction, text: str, mode: str) -> None:
        if not await self.authorize(interaction):
            return
        if not text.strip():
            await _send_error(
                interaction,
                "번역할 글이 없습니다. 글이 있는 메시지를 고르거나 /nuri에 문장을 넣어 주세요.",
            )
            return
        try:
            # Acknowledge before calling the model, within Discord's 3-second limit.
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = await self.service.run(interaction.user.id, text, mode)
            pages = build_text_pages(render_result(result))
            view = _PracticeView(self, interaction.user.id) if mode == "learn" else None
            await interaction.edit_original_response(
                content=pages[0],
                embeds=[],
                view=view,
                allowed_mentions=NO_MENTIONS,
            )
            for page in pages[1:]:
                await interaction.followup.send(
                    content=page,
                    embeds=[],
                    suppress_embeds=True,
                    ephemeral=True,
                    allowed_mentions=NO_MENTIONS,
                    wait=True,
                )
        except UserError as error:
            await _send_error(interaction, str(error))
        except Exception:
            LOGGER.warning("A Nuri request could not be completed.")
            await _send_error(
                interaction, "처리 중 문제가 생겼습니다. 잠시 후 문장을 나누어 다시 시도해 주세요."
            )

    async def on_ready(self) -> None:
        LOGGER.info("Nuri is connected to Discord.")
        print("Nuri가 Discord에 연결되었습니다. 창을 열어 두세요. 종료: Ctrl+C.", flush=True)

    async def on_error(self, event_method: str, *args: object, **kwargs: object) -> None:
        LOGGER.warning("A Discord event handler failed.")


async def run_bot(settings: Settings, service: NuriService, register: bool = False) -> None:
    """Register explicitly, or run without changing the command registry."""
    if not settings.discord_token:
        raise UserError("Discord 봇 토큰을 로컬 설정에 입력해 주세요.")
    client = NuriClient(settings, service)
    try:
        async with client:
            await client.login(settings.discord_token)
            if register:
                await client.tree.sync()
                print("Nuri 명령 등록이 완료되었습니다.", flush=True)
            else:
                await client.connect(reconnect=True)
    except UserError:
        raise
    except discord.LoginFailure:
        raise UserError("Discord 봇 토큰을 확인해 주세요. 로그인하지 못했습니다.") from None
    except discord.DiscordException:
        raise UserError("Discord에 연결하지 못했습니다. 앱 설정과 인터넷 연결을 확인해 주세요.") from None
    except OSError:
        raise UserError("인터넷 연결을 확인한 뒤 Nuri를 다시 실행해 주세요.") from None
    except Exception:
        raise UserError("Nuri를 시작하지 못했습니다. 설치 상태와 로컬 설정을 확인해 주세요.") from None
