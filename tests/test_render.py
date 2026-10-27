"""Content remains readable without rich embeds, including on mobile clients."""

import re
import unittest

from nuri.models import Expression, Result
from nuri.render import build_text_pages, render_result


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


class TextPageTests(unittest.TestCase):
    def test_short_learning_response_is_one_message_with_translation_first(self):
        result = Result("I am getting better.", "learn", "점점 나아지고 있어요.",
                        (Expression("get better", "나아지다"),))
        pages = build_text_pages(render_result(result))
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].startswith("**번역**\n점점 나아지고 있어요."))
        self.assertIn("get better — 나아지다", pages[0])
        self.assertIn("**원문**\nI am getting better.", pages[0])

    def test_practice_displays_correction_then_feedback_and_source(self):
        result = Result("I learns.", "practice", corrected="I learn.", feedback="learn을 써요.")
        page = build_text_pages(render_result(result))[0]
        self.assertTrue(page.startswith("**자연스럽게 다듬으면**\nI learn."))
        self.assertLess(page.index("learn을 써요."), page.index("I learns."))

    def test_source_and_model_markdown_cannot_hide_or_reformat_output(self):
        text = "||secret|| ```code``` **bold** [link](url)\n# heading\n> quote"
        page = build_text_pages([("번역", text)])[0]
        self.assertIn(r"\|\|secret\|\|", page)
        self.assertIn(r"\`\`\`code\`\`\`", page)
        self.assertIn(r"\*\*bold\*\*", page)
        self.assertIn(r"\[link\]\(url\)", page)
        self.assertNotRegex(page, r"(?<!\\)\|\||(?<!\\)`{3}")

    def test_unicode_preserved_and_each_content_page_fits_discord(self):
        text = "A한글🦊😀e\u0301\n" * 700
        pages = build_text_pages([("번역", text)])
        self.assertGreater(len(pages), 1)
        self.assertLessEqual(len(pages), 6)
        bodies = []
        for page in pages:
            self.assertLessEqual(utf16_length(page), 2000)
            body = re.sub(r"^\*\*Nuri · 계속 \d+\*\*\n\n", "", page)
            body = body.rsplit("\n\nNuri · 나에게만 표시 · ", 1)[0]
            bodies.append(body)
        self.assertEqual("".join(bodies), "**번역**\n" + text)

    def test_six_page_cap_warns_when_output_is_truncated(self):
        pages = build_text_pages([("번역", "🦊" * 9000)])
        self.assertEqual(len(pages), 6)
        self.assertIn("긴 출력 일부 생략", pages[-1])
        self.assertTrue(all(utf16_length(page) <= 2000 for page in pages))

    def test_empty_result_is_visible_content(self):
        self.assertIn("표시할 결과가 없습니다", build_text_pages([("빈 항목", "")])[0])

    def test_escaped_tokens_never_split_at_page_boundary(self):
        pages = build_text_pages([("번역", "|" * 3000)])
        for page in pages:
            body = re.sub(r"^\*\*Nuri · 계속 \d+\*\*\n\n", "", page)
            body = body.rsplit("\n\nNuri · 나에게만 표시 · ", 1)[0]
            self.assertFalse(body.endswith("\\"))
            self.assertNotRegex(body, r"(?<!\\)\|")


if __name__ == "__main__":
    unittest.main()
