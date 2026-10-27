import asyncio
import time

from .config import Settings
from .limits import DailyBudget
from .models import Expression, Result, UserError


class NuriService:
    def __init__(self, settings: Settings, provider):
        self.settings = settings
        self.provider = provider
        self.budget = DailyBudget(settings.state_dir / "usage.sqlite", settings.daily_request_limit)
        self.lock = asyncio.Lock()
        self.last_attempt: dict[int, float] = {}

    async def run(self, user_id: int, text: str, mode: str) -> Result:
        if mode not in ("translate", "learn", "practice"):
            raise UserError("번역·함께 배우기·한 문장 연습 중 하나를 선택해 주세요.")
        if not isinstance(text, str) or not text.strip():
            raise UserError("번역할 글이 없어요. 첨부파일 대신 문장을 선택하거나 입력해 주세요.")
        max_chars = 1000 if mode == "practice" else self.settings.max_input_chars
        if len(text) > max_chars:
            raise UserError(f"한 번에 {max_chars:,}자까지 사용할 수 있어요. 문단을 나눠 주세요.")
        if not self.settings.api_enabled or not self.settings.gemini_key:
            raise UserError("Google API 연결 설정이 아직 필요해요.")
        if self.lock.locked():
            raise UserError("다른 요청을 처리하고 있어요. 잠시 후 다시 시도해 주세요.")
        now = time.monotonic()
        if now - self.last_attempt.get(user_id, float("-inf")) < self.settings.cooldown_seconds:
            raise UserError(f"요청 사이에 {self.settings.cooldown_seconds}초만 기다려 주세요.")
        async with self.lock:
            self.budget.reserve()
            self.last_attempt[user_id] = now
            # An attempt counts even when the response fails: Google may have processed it.
            return await self.provider.generate(text, mode)
