"""Extract only text Discord supplied for the explicitly selected message."""

import re

from .models import UserError


_MENTION = re.compile(r"<@(?:!|&)?[0-9]+>|<#[0-9]+>|(?<!\w)@(?:everyone|here)\b")
MENTIONS_ONLY = (
    "선택한 메시지에는 멘션만 있고 번역할 본문이 없어요. "
    "본문이 있는 메시지를 선택하거나 /nuri에 글을 붙여 넣어 주세요."
)
NO_SELECTED_TEXT = (
    "선택한 메시지에서 번역할 본문을 찾지 못했어요. "
    "본문이 있는 메시지를 선택하거나 /nuri에 글을 붙여 넣어 주세요."
)


def selected_message_text(message: object) -> str:
    """Read content and visible embed text, never URLs or attachments.

    Mention IDs are routing metadata, not useful translation source. Remove
    their syntax without inventing names, while keeping surrounding prose.
    Repeated exact textual blocks (such as a duplicated link preview) occur once.
    The caller enforces its input-length limit on the complete extracted text.
    """
    if not isinstance(message, dict):
        raise UserError(NO_SELECTED_TEXT)
    pieces: list[str] = []
    seen: set[str] = set()
    had_mention = False

    def add(value: object) -> None:
        nonlocal had_mention
        if not isinstance(value, str):
            return
        had_mention = had_mention or bool(_MENTION.search(value))
        text = _MENTION.sub(" ", value).strip()
        if text and any(character.isalnum() for character in text) and text not in seen:
            pieces.append(text)
            seen.add(text)

    add(message.get("content"))
    embeds = message.get("embeds", [])
    if isinstance(embeds, list):
        for embed in embeds:
            if not isinstance(embed, dict):
                continue
            add(embed.get("title"))
            add(embed.get("description"))
            fields = embed.get("fields", [])
            if isinstance(fields, list):
                for field in fields:
                    if isinstance(field, dict):
                        add(field.get("name"))
                        add(field.get("value"))
    if not pieces:
        raise UserError(MENTIONS_ONLY if had_mention else NO_SELECTED_TEXT)
    return "\n\n".join(pieces)
