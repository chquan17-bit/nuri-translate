"""Private Discord interactions on Cloud Run, with a separately private worker.

The public ingress validates Discord signatures and responds within its deadline.
Translation runs inside a Cloud Tasks HTTP request, never after a response has
returned. Cloud Run IAM must allow only the task service identity on the worker.
Neither application logs nor durable usage records contain text or tokens.
"""

from __future__ import annotations

import base64
import asyncio
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import logging
import os
import re
import time

import aiohttp
from aiohttp import web
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .config import Settings
from .models import UserError
from .selected_message import selected_message_text


APPLICATION_ID = 1564099441110286398
EPHEMERAL = 64
SUPPRESS_EMBEDS = 4
PRACTICE_TTL = 600
MAX_TASK_AGE = 600  # Leave five minutes before Discord's webhook-token expiry.
NO_MENTIONS = {"parse": []}
GENERIC_ERROR = "처리 중 문제가 생겼습니다. 잠시 후 문장을 나누어 다시 시도해 주세요."
SNOWFLAKE = re.compile(r"[0-9]{16,22}\Z")


@dataclass(frozen=True)
class CloudConfig:
    role: str
    owner_id: int
    public_key: str = field(default="", repr=False)
    component_secret: str = field(default="", repr=False)
    project: str = ""
    location: str = "asia-northeast3"
    queue: str = "nuri-translation"
    worker_url: str = ""
    task_service_account: str = ""
    application_id: int = APPLICATION_ID

    def validate(self):
        if self.role not in ("ingress", "worker"):
            raise ValueError("NURI_ROLE must be ingress or worker")
        if not SNOWFLAKE.fullmatch(str(self.owner_id)):
            raise ValueError("NURI_OWNER_ID is required")
        if self.application_id != APPLICATION_ID:
            raise ValueError("Unexpected application")
        if len(self.component_secret.encode()) < 32:
            raise ValueError("NURI_COMPONENT_SECRET must be at least 32 bytes")
        if self.role == "ingress" and not re.fullmatch(r"[0-9a-fA-F]{64}", self.public_key):
            raise ValueError("DISCORD_PUBLIC_KEY is required")

    @classmethod
    def from_env(cls):
        try:
            owner = int(os.environ.get("NURI_OWNER_ID", ""))
        except ValueError:
            raise ValueError("NURI_OWNER_ID is required") from None
        result = cls(
            role=os.environ.get("NURI_ROLE", ""), owner_id=owner,
            public_key=os.environ.get("DISCORD_PUBLIC_KEY", "").strip(),
            component_secret=os.environ.get("NURI_COMPONENT_SECRET", ""),
            project=os.environ.get("CLOUD_TASKS_PROJECT", os.environ.get("NURI_CLOUD_PROJECT", "")),
            location=os.environ.get("CLOUD_TASKS_LOCATION", "asia-northeast3"),
            queue=os.environ.get("CLOUD_TASKS_QUEUE", "nuri-translation"),
            worker_url=os.environ.get("NURI_WORKER_URL", ""),
            task_service_account=os.environ.get("NURI_TASK_SERVICE_ACCOUNT", ""),
        )
        result.validate()
        return result


def private_error(message: str):
    return {"type": 4, "data": {"content": message, "flags": EPHEMERAL,
                                "allowed_mentions": NO_MENTIONS}}


def _component_id(kind: str, owner_id: int, expires: int, secret: str) -> str:
    prefix = f"nuri:{kind}:{owner_id}:{expires}"
    digest = hmac.new(secret.encode(), prefix.encode(), hashlib.sha256).digest()[:16]
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{prefix}:{signature}"


def _read_component(value: str, kind: str, owner_id: int, secret: str, now: float) -> int:
    try:
        prefix, got_kind, owner, expiry, signature = value.split(":")
        expires = int(expiry)
        expected = _component_id(kind, owner_id, expires, secret)
        if (prefix != "nuri" or got_kind != kind or owner != str(owner_id)
                or not hmac.compare_digest(value, expected)
                or expires <= now or expires > now + PRACTICE_TTL + 5):
            raise ValueError
        return expires
    except (ValueError, TypeError, AttributeError):
        raise UserError("연습 시간이 끝났거나 올바른 버튼이 아닙니다. Nuri를 다시 실행해 주세요.") from None


def _user_id(payload: dict) -> int:
    user = payload.get("user")
    if not isinstance(user, dict):
        member = payload.get("member")
        user = member.get("user") if isinstance(member, dict) else None
    try:
        return int(user["id"])
    except (TypeError, KeyError, ValueError):
        return 0


def _validate_text(settings: Settings, text: object, mode: object) -> str:
    if mode not in ("translate", "learn", "practice"):
        raise UserError("번역·함께 배우기·한 문장 연습 중 하나를 선택해 주세요.")
    if not isinstance(text, str) or not text.strip():
        raise UserError("번역할 글이 없어요. 첨부파일 대신 문장을 선택하거나 입력해 주세요.")
    limit = min(1000, settings.max_input_chars) if mode == "practice" else settings.max_input_chars
    if len(text) > limit:
        raise UserError(f"한 번에 {limit:,}자까지 사용할 수 있어요. 문단을 나눠 주세요.")
    return text


def _command(payload: dict) -> tuple[str, str]:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise UserError("올바른 Nuri 명령을 선택해 주세요.")
    if data.get("name") == "nuri" and data.get("type", 1) == 1:
        options = data.get("options", [])
        if not isinstance(options, list) or len(options) > 2:
            raise UserError("올바른 Nuri 명령을 선택해 주세요.")
        values = {item.get("name"): item.get("value") for item in options if isinstance(item, dict)}
        if values.get("mode", "learn") not in ("translate", "learn"):
            raise UserError("번역 또는 영어 학습을 선택해 주세요.")
        return values.get("text", ""), values.get("mode", "learn")
    if data.get("type") == 3 and data.get("name") in ("Nuri 번역", "Nuri와 영어 배우기"):
        target = str(data.get("target_id", ""))
        resolved = data.get("resolved", {})
        messages = resolved.get("messages", {}) if isinstance(resolved, dict) else {}
        message = messages.get(target, {}) if isinstance(messages, dict) else {}
        text = selected_message_text(message)
        return text, "learn" if data["name"] == "Nuri와 영어 배우기" else "translate"
    raise UserError("올바른 Nuri 명령을 선택해 주세요.")


def _modal_text(data: dict) -> str:
    rows = data.get("components", [])
    if not isinstance(rows, list):
        raise UserError("연습 문장을 다시 입력해 주세요.")
    for row in rows:
        if not isinstance(row, dict):
            continue
        children = row.get("components", [])
        if not isinstance(children, list):
            continue
        for child in children:
            if isinstance(child, dict) and child.get("custom_id") == "nuri_sentence":
                return child.get("value", "")
    raise UserError("연습 문장을 다시 입력해 주세요.")


class DiscordSender:
    def __init__(self, config: CloudConfig, *, clock=time.time):
        self.config = config
        self.clock = clock

    async def _request(self, session, method: str, url: str, value: dict):
        try:
            async with session.request(method, url, json=value, allow_redirects=False) as response:
                if response.status not in (200, 204):
                    raise UserError("Discord에 개인 응답을 전달하지 못했습니다.")
        except (aiohttp.ClientError, TimeoutError):
            raise UserError("Discord에 개인 응답을 전달하지 못했습니다.") from None

    def _url(self, task: dict):
        return f"https://discord.com/api/v10/webhooks/{self.config.application_id}/{task['token']}"

    async def error(self, task: dict, message: str):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10), trust_env=False) as session:
            await self._request(session, "PATCH", self._url(task) + "/messages/@original", {
                "content": message[:1800], "embeds": [], "components": [],
                "allowed_mentions": NO_MENTIONS,
            })

    async def result(self, task: dict, result):
        from .render import build_text_pages, render_result
        pages = build_text_pages(render_result(result))
        components = []
        if task["mode"] == "learn":
            expires = int(self.clock()) + PRACTICE_TTL
            components = [{"type": 1, "components": [{
                "type": 2, "style": 1, "label": "한 문장 써보기",
                "custom_id": _component_id("p", self.config.owner_id, expires, self.config.component_secret),
            }]}]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10), trust_env=False) as session:
            await self._request(session, "PATCH", self._url(task) + "/messages/@original", {
                "content": pages[0], "embeds": [], "components": components,
                "flags": SUPPRESS_EMBEDS,
                "allowed_mentions": NO_MENTIONS,
            })
            for page in pages[1:]:
                await self._request(session, "POST", self._url(task) + "?wait=true", {
                    "content": page, "embeds": [], "flags": EPHEMERAL | SUPPRESS_EMBEDS,
                    "allowed_mentions": NO_MENTIONS,
                })


def create_app(config: CloudConfig, settings: Settings | None = None, *,
               queue=None, provider=None, state=None, sender=None, clock=time.time) -> web.Application:
    """Dependency-injected factory for offline boundary tests and deployment."""
    config.validate()
    settings = settings or Settings.from_env()
    if settings.expected_application_id != config.application_id:
        raise ValueError("Unexpected application")
    if config.role == "ingress" and queue is None:
        from .cloud_queue import CloudTasksQueue
        queue = CloudTasksQueue(config.project, config.location, config.queue,
                                config.worker_url, config.task_service_account, clock=clock)
    if config.role == "worker":
        if not settings.api_enabled or not settings.gemini_key:
            raise ValueError("Worker Gemini configuration is missing")
        if provider is None:
            from .provider import GeminiProvider
            provider = GeminiProvider(settings)
        if state is None:
            from .cloud_state import CloudState
            state = CloudState(settings)
        sender = sender or DiscordSender(config, clock=clock)

    @web.middleware
    async def safe_errors(request, handler):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception:
            # Never let aiohttp format an exception with request/token context.
            print(json.dumps({"event": "request_failed", "role": config.role}), flush=True)
            return web.json_response({"error": "request_failed"}, status=500)

    app = web.Application(client_max_size=65536, middlewares=[safe_errors])

    async def health(request):
        return web.json_response({"ok": True, "role": config.role})

    async def interactions(request):
        raw = await request.read()
        stamp = request.headers.get("X-Signature-Timestamp", "")
        signature = request.headers.get("X-Signature-Ed25519", "")
        try:
            if not stamp.isascii() or not stamp.isdecimal() or abs(clock() - int(stamp)) > 300:
                raise ValueError
            VerifyKey(bytes.fromhex(config.public_key)).verify(stamp.encode() + raw, bytes.fromhex(signature))
        except (ValueError, TypeError, BadSignatureError):
            return web.json_response({"error": "invalid_signature"}, status=401)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return web.json_response({"error": "invalid_request"}, status=400)
        if not isinstance(payload, dict) or str(payload.get("application_id")) != str(config.application_id):
            return web.json_response({"error": "invalid_application"}, status=401)
        if payload.get("type") == 1:
            return web.json_response({"type": 1})
        if _user_id(payload) != config.owner_id:
            return web.json_response(private_error("현재 Nuri는 소유자만 사용할 수 있습니다."))
        try:
            interaction_type = payload.get("type")
            data = payload.get("data", {})
            if not isinstance(data, dict):
                raise UserError("올바른 Nuri 명령을 선택해 주세요.")
            if interaction_type == 3:
                expires = _read_component(data.get("custom_id", ""), "p", config.owner_id,
                                          config.component_secret, clock())
                return web.json_response({"type": 9, "data": {
                    "title": "Nuri와 한 문장 써보기",
                    "custom_id": _component_id("m", config.owner_id, expires, config.component_secret),
                    "components": [{"type": 1, "components": [{
                        "type": 4, "custom_id": "nuri_sentence", "label": "내 영어 문장",
                        "style": 2, "placeholder": "배운 표현으로 영어 한 문장을 써 보세요.",
                        "required": True, "min_length": 1, "max_length": min(1000, settings.max_input_chars),
                    }]}],
                }})
            if interaction_type == 5:
                _read_component(data.get("custom_id", ""), "m", config.owner_id,
                                config.component_secret, clock())
                text, mode = _modal_text(data), "practice"
            elif interaction_type == 2:
                text, mode = _command(payload)
            else:
                raise UserError("지원하지 않는 Nuri 요청입니다.")
            text = _validate_text(settings, text, mode)
            interaction_id = str(payload.get("id", ""))
            token = payload.get("token", "")
            if (not SNOWFLAKE.fullmatch(interaction_id) or not isinstance(token, str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,2048}", token)):
                raise UserError("Discord 요청을 확인하지 못했습니다. 다시 실행해 주세요.")
            await queue.enqueue({
                "application_id": str(config.application_id), "interaction_id": interaction_id,
                "user_id": str(config.owner_id), "token": token,
                "text": text, "mode": mode, "created_at": int(clock()),
            })
            print(json.dumps({"event": "command_accepted", "mode": mode}), flush=True)
            return web.json_response({"type": 5, "data": {"flags": EPHEMERAL}})
        except UserError as error:
            return web.json_response(private_error(str(error)))

    async def tasks(request):
        # The worker service is private at Cloud Run IAM. Headers alone must
        # never be used as authentication; ingress has no route to this handler.
        try:
            task = await request.json()
            if not isinstance(task, dict):
                raise ValueError
            if (str(task.get("application_id")) != str(config.application_id)
                    or str(task.get("user_id")) != str(config.owner_id)
                    or not SNOWFLAKE.fullmatch(str(task.get("interaction_id", "")))
                    or not isinstance(task.get("token"), str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,2048}", task["token"])
                    or not isinstance(task.get("created_at"), int)
                    or not -5 <= clock() - task["created_at"] <= MAX_TASK_AGE):
                raise ValueError
        except (ValueError, TypeError, UnicodeDecodeError):
            return web.json_response({"error": "invalid_task"}, status=400)
        reserved = False
        phase = "validate"
        try:
            # Cloud Run request timeouts alone do not terminate Python work.
            # Bound actual work below CloudState's 300-second global lease.
            async with asyncio.timeout(210):
                text = _validate_text(settings, task.get("text"), task.get("mode"))
                phase = "reserve"
                reserved = await state.reserve(task["interaction_id"])
                if not reserved:
                    return web.json_response({"ok": True, "duplicate": True})
                phase = "provider"
                result = await provider.generate(text, task["mode"])
                phase = "discord_send"
                await sender.result(task, result)
                print(json.dumps({"event": "translation_completed", "mode": task["mode"]}), flush=True)
        except UserError as error:
            try:
                await sender.error(task, str(error))
            except Exception:
                pass
            print(json.dumps({"event": "translation_rejected", "phase": phase}), flush=True)
        except Exception:
            try:
                await sender.error(task, GENERIC_ERROR)
            except Exception:
                pass
            print(json.dumps({"event": "translation_failed", "phase": phase}), flush=True)
        finally:
            if reserved:
                try:
                    await state.finish(task["interaction_id"])
                except Exception:
                    print(json.dumps({"event": "quota_lease_release_failed"}), flush=True)
        # No task retry: an upstream model may already have processed the input.
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_get("/healthz", health)
    if config.role == "ingress":
        app.router.add_post("/interactions", interactions)
        if hasattr(queue, "close"):
            async def close_queue(app):
                await queue.close()
            app.on_cleanup.append(close_queue)
    else:
        app.router.add_post("/tasks", tasks)
    return app


def main():
    logging.disable(logging.CRITICAL)
    try:
        config = CloudConfig.from_env()
        app = create_app(config)
        port = int(os.environ.get("PORT", "8080"))
    except Exception:
        print(json.dumps({"event": "startup_configuration_invalid"}), flush=True)
        raise SystemExit(2) from None
    web.run_app(app, host="0.0.0.0", port=port, access_log=None, print=None)


if __name__ == "__main__":
    main()
