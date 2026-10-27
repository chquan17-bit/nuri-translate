"""Small Cloud Tasks REST adapter; request bodies and credentials are never logged."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

import aiohttp

from .models import UserError


QUEUE_ERROR = "번역 요청을 전달하지 못했어요. 잠시 후 다시 시도해 주세요."


class CloudTasksQueue:
    def __init__(self, project: str, location: str, queue: str,
                 worker_url: str, service_account: str, *, clock=time.time):
        for value in (project, location, queue):
            if not re.fullmatch(r"[a-z][a-z0-9-]{1,62}", value):
                raise ValueError("Invalid Cloud Tasks configuration")
        parsed = urlsplit(worker_url)
        if (parsed.scheme != "https" or not parsed.hostname
                or not parsed.hostname.endswith(".run.app")
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or parsed.username or parsed.port):
            raise ValueError("Invalid worker endpoint")
        if not re.fullmatch(r"[a-z][a-z0-9-]*@[a-z][a-z0-9-]*\.iam\.gserviceaccount\.com", service_account):
            raise ValueError("Invalid task service account")
        self.parent = f"projects/{project}/locations/{location}/queues/{queue}"
        self.worker_url = worker_url.rstrip("/")
        self.service_account = service_account
        self.clock = clock
        self._credentials = None
        self._auth_lock = asyncio.Lock()
        self._refresh_task = None
        self._session = None

    async def _token(self) -> str:
        async with self._auth_lock:
            def load_and_refresh():
                # ADC uses the Cloud Run service identity, without a key file.
                import google.auth
                from google.auth.transport.requests import Request
                if self._credentials is None:
                    self._credentials, _ = google.auth.default(
                        scopes=["https://www.googleapis.com/auth/cloud-platform"])
                if not self._credentials.valid:
                    self._credentials.refresh(Request())
                return self._credentials.token
            if self._refresh_task is None or self._refresh_task.done():
                self._refresh_task = asyncio.create_task(asyncio.to_thread(load_and_refresh))
            # A timed-out caller must not start a second credential-refresh thread.
            return await asyncio.wait_for(asyncio.shield(self._refresh_task), 1.0)

    async def enqueue(self, payload: dict) -> bool:
        """Bound the entire admission path, including credential-lock contention."""
        try:
            async with asyncio.timeout(2.3):
                return await self._enqueue(payload)
        except asyncio.TimeoutError:
            raise UserError(QUEUE_ERROR) from None

    async def _enqueue(self, payload: dict) -> bool:
        """True for a new task; False for an already accepted interaction.

        Creating a task is bounded and never retried here. A stable task ID also
        makes a Discord delivery retry safe when an HTTP response is lost.
        """
        task_id = "nuri-" + hashlib.sha256(payload["interaction_id"].encode("ascii")).hexdigest()
        task = {
            "name": f"{self.parent}/tasks/{task_id}",
            "scheduleTime": datetime.fromtimestamp(self.clock() + 2, timezone.utc).isoformat(),
            "dispatchDeadline": "270s",
            "httpRequest": {
                "httpMethod": "POST",
                "url": self.worker_url + "/tasks",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode("ascii"),
                "oidcToken": {
                    "serviceAccountEmail": self.service_account,
                    "audience": self.worker_url,
                },
            },
        }
        try:
            token = await self._token()
            # Start this delay after credential lookup, so the bounded API call
            # returns before the worker can attempt the initial response edit.
            task["scheduleTime"] = datetime.fromtimestamp(self.clock() + 2, timezone.utc).isoformat()
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=1.3), trust_env=False)
            async with self._session.post(
                    f"https://cloudtasks.googleapis.com/v2/{self.parent}/tasks",
                    headers={"Authorization": "Bearer " + token},
                    json={"task": task}, allow_redirects=False) as response:
                # Error bodies can contain request metadata; never read/log them.
                if response.status == 409:
                    return False
                if response.status == 200:
                    return True
                raise UserError(QUEUE_ERROR)
        except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
            raise UserError(QUEUE_ERROR) from None
        except UserError:
            raise
        except Exception:
            raise UserError(QUEUE_ERROR) from None

    async def close(self):
        if self._session is not None:
            await self._session.close()
