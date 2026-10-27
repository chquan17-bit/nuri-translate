from dataclasses import dataclass, field
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    gemini_key: str = field(default="", repr=False)
    discord_token: str = field(default="", repr=False)
    expected_application_id: int = 1564099441110286398
    model: str = "gemini-3.5-flash-lite"
    api_enabled: bool = False
    allowed_user_ids: frozenset[int] = frozenset()
    max_input_chars: int = 3000
    daily_request_limit: int = 25
    cooldown_seconds: int = 10
    state_dir: Path = ROOT / ".state"
    timeout_seconds: int = 90

    @classmethod
    def from_env(cls):
        def bounded(name, default, low, high):
            try:
                value = int(os.environ.get(name, default))
            except ValueError:
                raise ValueError(f"{name}: 정수가 필요합니다.") from None
            if not low <= value <= high:
                raise ValueError(f"{name}: {low}~{high} 범위가 필요합니다.")
            return value

        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
        if not re.fullmatch(r"gemini-[a-z0-9.-]+", model):
            raise ValueError("GEMINI_MODEL 형식이 올바르지 않습니다.")
        ids = os.environ.get("NURI_ALLOWED_USER_IDS", "").strip()
        try:
            allowed = frozenset(int(x.strip()) for x in ids.split(",") if x.strip())
            if any(x <= 0 for x in allowed):
                raise ValueError
        except ValueError:
            raise ValueError("NURI_ALLOWED_USER_IDS에는 Discord 사용자 ID만 입력하세요.") from None
        return cls(
            gemini_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            discord_token=os.environ.get("DISCORD_BOT_TOKEN", "").strip(),
            model=model,
            api_enabled=os.environ.get("NURI_API_ENABLED", "false").lower() == "true",
            allowed_user_ids=allowed,
            daily_request_limit=bounded("NURI_DAILY_REQUEST_LIMIT", 25, 1, 1000),
            cooldown_seconds=bounded("NURI_COOLDOWN_SECONDS", 10, 1, 600),
        )
