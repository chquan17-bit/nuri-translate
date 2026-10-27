from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path
import sqlite3

from .models import UserError


class DailyBudget:
    """Persist only date and number of attempts; no text, user IDs or API keys."""
    def __init__(self, path: Path, limit: int):
        self.path = path
        self.limit = limit

    def reserve(self, day: str | None = None):
        day = day or datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(self.path, timeout=3)) as db:
                with db:
                    db.execute("CREATE TABLE IF NOT EXISTS daily (day TEXT PRIMARY KEY, attempts INTEGER NOT NULL)")
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute("SELECT attempts FROM daily WHERE day = ?", (day,)).fetchone()
                    if row and row[0] >= self.limit:
                        raise UserError("오늘의 Nuri 요청 한도에 도달했어요. 한국 시간 자정에 다시 사용할 수 있어요.")
                    db.execute("INSERT INTO daily VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET attempts = attempts + 1", (day,))
        except (sqlite3.Error, OSError):
            raise UserError("사용량 기록을 확인하지 못해 요청을 멈췄어요. Nuri 저장 폴더를 확인해 주세요.") from None
