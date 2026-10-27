import argparse
import asyncio
import json
import logging
import sys

from .config import Settings


def main():
    parser = argparse.ArgumentParser(description="Nuri 번역 · QUAN CHENGHAO · 권성호")
    parser.add_argument("command", choices=("doctor", "register", "run"), nargs="?", default="doctor")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(str(error))
        return 2
    if args.command == "doctor":
        print(json.dumps({"model": settings.model,
            "discord_token_present": bool(settings.discord_token),
            "gemini_key_present": bool(settings.gemini_key),
            "api_enabled": settings.api_enabled,
            "default_access": "application owner only",
            "additional_allowed_users": len(settings.allowed_user_ids),
            "daily_attempt_limit": settings.daily_request_limit,
            "request_content_saved": False,
            "live_connection_tested": False}, indent=2))
        return 0
    if not settings.discord_token:
        print("Discord 앱 연결이 필요합니다. scripts/Configure-Nuri.ps1을 사용해 주세요.")
        return 2
    if args.command == "run" and (not settings.gemini_key or not settings.api_enabled):
        print("Google API 키와 이용 티어 확인이 필요합니다. 연결 설정을 완료해 주세요.")
        return 2
    # The library's default error tracebacks can include HTTP request details.
    logging.disable(logging.CRITICAL)
    from .discord_app import run_bot
    from .provider import GeminiProvider
    from .service import NuriService
    try:
        asyncio.run(run_bot(settings, NuriService(settings, GeminiProvider(settings)),
                            register=args.command == "register"))
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Nuri 연결을 완료하지 못했습니다. 토큰, 앱 설치, 네트워크를 확인해 주세요. 비밀 값은 표시하지 않습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
