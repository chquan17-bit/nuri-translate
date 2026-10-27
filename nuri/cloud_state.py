"""Atomic, content-free limits for the Cloud Run worker.

Cloud Run instances and revisions can overlap. A local SQLite file or process
lock therefore cannot enforce Nuri's daily limit. Firestore transactions keep
one global lease, a counter per Korean calendar day, and hashed interaction
markers. They never store source text, model output, user IDs, or credentials.

A reserved interaction is never sent to the model a second time, including
after a worker crash. This intentionally favours a missed response over an
unbounded or duplicate paid operation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import math
import os
import re
import time
from typing import Any, Callable, Protocol, TypeVar

from .config import Settings
from .models import UserError


KST = timezone(timedelta(hours=9))
COLLECTION = "nuri_limits"
GLOBAL_DOCUMENT = "global"
STATE_ERROR = "사용량 기록을 확인하지 못해 요청을 멈췄어요. 잠시 후 다시 시도해 주세요."
LIMIT_ERROR = "오늘의 Nuri 요청 한도에 도달했어요. 한국 시간 자정에 다시 사용할 수 있어요."
BUSY_ERROR = "다른 요청을 처리하고 있어요. 잠시 후 다시 시도해 주세요."
T = TypeVar("T")


class _Transaction(Protocol):
    def get(self, name: str) -> dict[str, Any] | None: ...

    def set(self, name: str, value: dict[str, Any]) -> None: ...


class _Backend(Protocol):
    def transact(self, callback: Callable[[_Transaction], T]) -> T: ...


class _FirestoreTransaction:
    def __init__(self, collection: Any, transaction: Any) -> None:
        self.collection = collection
        self.transaction = transaction

    def get(self, name: str) -> dict[str, Any] | None:
        snapshot = self.collection.document(name).get(
            transaction=self.transaction, retry=None, timeout=5.0
        )
        return snapshot.to_dict() if snapshot.exists else None

    def set(self, name: str, value: dict[str, Any]) -> None:
        self.transaction.set(self.collection.document(name), value)


class _FirestoreBackend:
    def __init__(self, client: Any = None, project_id: str | None = None) -> None:
        # Lazy imports let the local gateway and offline tests run without the
        # optional Google SDK, and avoid contacting metadata at module import.
        from google.cloud import firestore

        self.firestore = firestore
        self.client = client or firestore.Client(project=project_id)
        self.collection = self.client.collection(COLLECTION)

    def transact(self, callback: Callable[[_Transaction], T]) -> T:
        @self.firestore.transactional
        def execute(transaction: Any) -> T:
            return callback(_FirestoreTransaction(self.collection, transaction))

        return execute(self.client.transaction(max_attempts=3))


def _request_hash(interaction_id: str) -> str:
    # Discord snowflakes fit in uint64. No raw identifier is persisted.
    if (
        not isinstance(interaction_id, str)
        or not re.fullmatch(r"[1-9][0-9]{0,19}", interaction_id)
        or int(interaction_id) > (1 << 64) - 1
    ):
        raise UserError("Discord 요청을 확인하지 못했어요. Nuri를 다시 실행해 주세요.")
    return hashlib.sha256(interaction_id.encode("ascii")).hexdigest()


def _number(value: Any, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid stored numeric metadata")
    if not math.isfinite(value) or value < minimum:
        raise ValueError("Invalid stored numeric metadata")
    return float(value)


class CloudState:
    """Reserve before generating, and finish in the worker's finally block.

``reserve`` returns False for any previously reserved interaction, without
charging another attempt or releasing another worker's lease. ``finish`` does
not refund an attempt: the model could have processed a failed request.

The lease must outlive actual application work, not just Cloud Run's request
timeout. The worker bounds work to 210 seconds, error delivery to 10 seconds,
and lease release to 20 seconds, below this 300-second lease. A crashed worker
recovers after that lease.
"""

    def __init__(
        self,
        settings: Settings,
        client: Any = None,
        *,
        project_id: str | None = None,
        backend: _Backend | None = None,
        clock: Callable[[], float] | None = None,
        lease_seconds: int = 300,
        transaction_timeout_seconds: float = 20.0,
    ) -> None:
        if lease_seconds < settings.timeout_seconds + 30:
            raise ValueError("Cloud lease must exceed the model timeout")
        self.settings = settings
        self._client = client
        self._backend = backend
        self.project_id = (
            project_id
            or os.environ.get("NURI_CLOUD_PROJECT")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        self.clock = clock or time.time
        self.lease_seconds = lease_seconds
        self.transaction_timeout_seconds = transaction_timeout_seconds

    def _transact(self, callback: Callable[[_Transaction], T]) -> T:
        if self._backend is None:
            self._backend = _FirestoreBackend(self._client, self.project_id)
        return self._backend.transact(callback)

    async def _call(self, callback: Callable[[], T]) -> T:
        try:
            # A timed-out thread might still commit. Its interaction marker
            # prevents a subsequent delivery from calling the model again.
            async with asyncio.timeout(self.transaction_timeout_seconds):
                return await asyncio.to_thread(callback)
        except UserError:
            raise
        except Exception:
            # Never attach the Google exception, URL, metadata, or credentials.
            raise UserError(STATE_ERROR) from None

    async def reserve(self, interaction_id: str) -> bool:
        request_hash = _request_hash(interaction_id)

        def reserve_transaction(transaction: _Transaction) -> bool:
            now = _number(self.clock())
            day = datetime.fromtimestamp(now, KST).date().isoformat()
            request_document = f"request_{request_hash}"
            existing = transaction.get(request_document)
            if existing is not None:
                # Even an unfinished marker is a no-op. We cannot know whether
                # a terminated worker already reached the external provider.
                return False

            global_state = transaction.get(GLOBAL_DOCUMENT) or {}
            daily_document = f"day_{day}"
            daily_state = transaction.get(daily_document) or {}
            busy_until = _number(global_state.get("busy_until", 0))
            if busy_until > now:
                raise UserError(BUSY_ERROR)

            previous_attempt = global_state.get("last_attempt_at")
            if previous_attempt is not None:
                elapsed = now - _number(previous_attempt)
                if elapsed < self.settings.cooldown_seconds:
                    raise UserError(
                        f"요청 사이에 {self.settings.cooldown_seconds}초만 기다려 주세요."
                    )

            attempts = daily_state.get("attempts", 0)
            if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
                raise ValueError("Invalid stored attempts")
            if attempts >= self.settings.daily_request_limit:
                raise UserError(LIMIT_ERROR)

            # All reads occur before all writes, as required by Firestore.
            transaction.set(daily_document, {"day": day, "attempts": attempts + 1})
            transaction.set(
                GLOBAL_DOCUMENT,
                {
                    "active_hash": request_hash,
                    "busy_until": now + self.lease_seconds,
                    "last_attempt_at": now,
                },
            )
            transaction.set(
                request_document,
                {"day": day, "started_at": now, "status": "reserved"},
            )
            return True

        return await self._call(lambda: self._transact(reserve_transaction))

    async def finish(self, interaction_id: str) -> None:
        request_hash = _request_hash(interaction_id)

        def finish_transaction(transaction: _Transaction) -> None:
            request_document = f"request_{request_hash}"
            existing = transaction.get(request_document)
            if existing is None or existing.get("status") == "finished":
                return
            global_state = transaction.get(GLOBAL_DOCUMENT) or {}
            now = _number(self.clock())
            # Completion of an expired older lease cannot unlock a newer job.
            if global_state.get("active_hash") == request_hash:
                global_state = dict(global_state)
                global_state["active_hash"] = ""
                global_state["busy_until"] = 0.0
                transaction.set(GLOBAL_DOCUMENT, global_state)
            transaction.set(
                request_document,
                {
                    "day": existing["day"],
                    "started_at": existing["started_at"],
                    "finished_at": now,
                    "status": "finished",
                },
            )

        await self._call(lambda: self._transact(finish_transaction))
