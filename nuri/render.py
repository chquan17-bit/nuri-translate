from .models import Result


MAX_RESPONSE_PAGES = 6  # Initial response plus five user-install followups.
_TEXT_BODY_UNITS = 1800  # Leave room for continuation and private-response labels.
_MARKDOWN_CHARACTERS = frozenset("\\`*_~|[]()<>#")


def render_result(result: Result) -> list[tuple[str, str]]:
    if result.mode == "practice":
        return [("자연스럽게 다듬으면", result.corrected), ("핵심 한 가지", result.feedback),
                ("내가 쓴 문장", result.source)]
    sections = [("번역", result.translation)]
    if result.expressions:
        sections.append(("다시 쓸 표현", "\n".join(f"{x.phrase} — {x.meaning}" for x in result.expressions)))
    return sections + [("원문", result.source)]


def build_text_pages(sections: list[tuple[str, str]]) -> list[str]:
    """Visible message content even when a Discord client hides rich embeds.

    Keep an escaped character together across page boundaries, so a source
    spoiler delimiter or code fence can never become active after splitting.
    Discord's character limits are counted conservatively as UTF-16 units.
    """
    tokens: list[str] = []
    for title, body in sections:
        if not body:
            continue
        if tokens:
            tokens.extend("\n\n")
        safe_title = "".join("\\" + c if c in _MARKDOWN_CHARACTERS else c for c in title)
        tokens.extend(f"**{safe_title}**\n")
        tokens.extend("\\" + c if c in _MARKDOWN_CHARACTERS else c for c in str(body))
    if not tokens:
        tokens.extend("표시할 결과가 없습니다. 문장을 바꿔 다시 시도해 주세요.")

    bodies: list[str] = []
    current: list[str] = []
    units = 0
    for token in tokens:
        size = sum(2 if ord(c) > 0xFFFF else 1 for c in token)
        if units + size > _TEXT_BODY_UNITS:
            bodies.append("".join(current))
            current, units = [], 0
        current.append(token)
        units += size
    if current:
        bodies.append("".join(current))

    truncated = len(bodies) > MAX_RESPONSE_PAGES
    bodies = bodies[:MAX_RESPONSE_PAGES]
    pages = []
    for index, body in enumerate(bodies, start=1):
        prefix = f"**Nuri · 계속 {index}**\n\n" if index > 1 else ""
        footer = f"Nuri · 나에게만 표시 · {index}/{len(bodies)}"
        if truncated and index == len(bodies):
            footer += "\n긴 출력 일부 생략: 문장을 나누어 다시 요청해 주세요."
        pages.append(f"{prefix}{body}\n\n{footer}")
    return pages
