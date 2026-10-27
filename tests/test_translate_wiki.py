"""Offline checks for safe, incremental documentation translation."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

from scripts import translate_wiki as wiki


def fake_translate(lines, language):
    word = "Translated" if language == "en" else "翻译"
    return [re.sub(r"[가-힣]+", word, line) for line in lines]


def payload(texts, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps({
        "translations": [{"id": f"s{i:04d}", "text": text} for i, text in enumerate(texts)]})}]}}]}


class WikiTranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs/wiki").mkdir(parents=True)
        (self.root / "docs/assets").mkdir(parents=True)
        self.write("docs/wiki/Home-ko.md", "# 문서\n\n한국어 설명입니다.\n")
        self.write("docs/wiki/Home-en.md", "# Documentation\n\nReviewed English.\n")
        self.write("docs/wiki/Home-zh-CN.md", "# 文档\n\n经过审核的中文。\n")

    def write(self, relative, text):
        (self.root / relative).write_text(text, encoding="utf-8")

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_seed_then_unchanged_and_check_do_not_need_key_or_network(self):
        wiki.synchronize(self.root, seed=True)
        before = self.snapshot()
        never = Mock(side_effect=AssertionError("model must not be called"))
        with patch.dict("os.environ", {}, clear=True):
            result = wiki.synchronize(self.root, translate=never)
            self.assertEqual(result["translated"], [])
            wiki.synchronize(self.root, check=True, translate=never)
        never.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_changed_source_updates_both_targets_and_cache(self):
        wiki.synchronize(self.root, seed=True)
        self.write("docs/wiki/Home-ko.md", "# 새로운 문서\n\n하루 25회입니다.\n")
        translate = Mock(side_effect=fake_translate)
        result = wiki.synchronize(self.root, translate=translate)
        self.assertEqual(result["translated"], ["docs/wiki/Home-en.md", "docs/wiki/Home-zh-CN.md"])
        self.assertEqual(translate.call_count, 2)
        self.assertIn("25", self.read("docs/wiki/Home-en.md"))
        wiki.synchronize(self.root, check=True)

    def test_only_tampered_or_missing_target_is_regenerated(self):
        wiki.synchronize(self.root, seed=True)
        self.write("docs/wiki/Home-en.md", "Manual edit\n")
        translate = Mock(side_effect=fake_translate)
        wiki.synchronize(self.root, translate=translate)
        self.assertEqual(translate.call_count, 1)
        self.assertEqual(translate.call_args.args[1], "en")
        (self.root / "docs/wiki/Home-zh-CN.md").unlink()
        with self.assertRaisesRegex(wiki.TranslationError, "stale"):
            wiki.synchronize(self.root, check=True)
        translate.reset_mock()
        wiki.synchronize(self.root, translate=translate)
        self.assertEqual(translate.call_count, 1)
        self.assertEqual(translate.call_args.args[1], "zh-CN")

    def test_new_source_creates_counterparts(self):
        wiki.synchronize(self.root, seed=True)
        self.write("docs/wiki/Guide.md", "# 안내\n\n새로운 내용입니다.\n")
        result = wiki.synchronize(self.root, translate=fake_translate)
        self.assertEqual(result["translated"], ["docs/wiki/Guide-en.md", "docs/wiki/Guide-zh-CN.md"])
        wiki.synchronize(self.root, check=True)

    def test_failure_after_first_language_leaves_every_file_untouched(self):
        wiki.synchronize(self.root, seed=True)
        self.write("docs/wiki/Home-ko.md", "# 새 문서\n\n바뀐 문장입니다.\n")
        before = self.snapshot()
        translate = Mock(side_effect=lambda lines, language: fake_translate(lines, language) if language == "en" else [])
        with self.assertRaises(wiki.TranslationError):
            wiki.synchronize(self.root, translate=translate)
        self.assertEqual(before, self.snapshot())

    def test_removed_source_only_removes_previously_managed_targets(self):
        self.write("docs/wiki/Guide.md", "# 안내\n")
        self.write("docs/wiki/Guide-en.md", "# Guide\n")
        self.write("docs/wiki/Guide-zh-CN.md", "# 指南\n")
        wiki.synchronize(self.root, seed=True)
        self.write("docs/wiki/Unmanaged-en.md", "Retain this\n")
        (self.root / "docs/wiki/Guide.md").unlink()
        result = wiki.synchronize(self.root, translate=Mock(side_effect=AssertionError))
        self.assertEqual(result["removed"], ["docs/wiki/Guide-en.md", "docs/wiki/Guide-zh-CN.md"])
        self.assertTrue((self.root / "docs/wiki/Unmanaged-en.md").exists())
        wiki.synchronize(self.root, check=True)

    def test_pipeline_version_change_invalidates_cache(self):
        wiki.synchronize(self.root, seed=True)
        with patch.object(wiki, "TRANSLATOR_VERSION", wiki.TRANSLATOR_VERSION + 1):
            with self.assertRaisesRegex(wiki.TranslationError, "stale"):
                wiki.synchronize(self.root, check=True)
            translate = Mock(side_effect=fake_translate)
            wiki.synchronize(self.root, translate=translate)
            self.assertEqual(translate.call_count, 2)

    def test_markdown_protects_code_markup_numbers_labels_and_localizes_content_links(self):
        source = (
            "[언어 선택](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)\n\n"
            "# 문서\n\n"
            "<details>\n\n"
            "**Nuri 번역**: 하루 25회, `Nuri와 영어 배우기`와 한 문장 써보기.\n"
            "| 안내 | [시작](Guide.md#section) |\n"
            "![구조](../assets/architecture-ko.svg)\n\n"
            "```powershell\nWrite-Output '번역하지 않는 코드 123'\n```\n\n"
            "</details>\n"
        )
        sources = {"docs/wiki/Home-ko.md": source, "docs/wiki/Guide.md": '<a id="section"></a>\n# 안내', "docs/assets/architecture-ko.svg": "svg"}
        result = wiki.translate_markdown(source, "docs/wiki/Home-ko.md", "en", sources, fake_translate)
        self.assertTrue(result.startswith(source.split("\n")[0].replace("[언어 선택]", "[Language selection]")))
        self.assertIn("```powershell\nWrite-Output '번역하지 않는 코드 123'\n```", result)
        self.assertIn("**Nuri 번역**", result)
        self.assertIn("`Nuri와 영어 배우기`", result)
        self.assertIn("한 문장 써보기", result)
        self.assertIn("25", result)
        self.assertIn("(Guide-en.md#section)", result)
        self.assertIn("(../assets/architecture-en.svg)", result)
        self.assertEqual(result.count("|"), source.count("|"))
        self.assertIn("<details>", result)

    def test_angle_wrapped_destinations_reference_links_and_nested_masks_restore(self):
        source = '[안내](<Guide.md#section>)\n\n[참고][ref]\n\n[ref]: <Guide.md> "설명"\n'
        sources = {"docs/wiki/Home-ko.md": source, "docs/wiki/Guide.md": '<a id="section"></a>\n# 안내'}
        result = wiki.translate_markdown(source, "docs/wiki/Home-ko.md", "en", sources, fake_translate)
        self.assertIn("(<Guide-en.md#section>)", result)
        self.assertIn('[ref]: <Guide-en.md> "설명"', result)
        self.assertNotIn("⟦NURI_", result)
        masked = wiki.MaskedText("⟦NURI_000001⟧", {"⟦NURI_000000⟧": "original", "⟦NURI_000001⟧": "nested ⟦NURI_000000⟧"})
        self.assertEqual(masked.restore(masked.text), "nested original")

    def test_indented_code_is_preserved_and_translated_heading_fragments_require_explicit_ids(self):
        source = '# 문서\n\n    print("한국어")\n\n\tprint("한국어")\n\n일반 문장입니다.\n'
        result = wiki.translate_markdown(source, "docs/wiki/Home-ko.md", "en", {"docs/wiki/Home-ko.md": source}, fake_translate)
        self.assertIn('    print("한국어")', result)
        self.assertIn('\tprint("한국어")', result)
        self.assertNotIn("일반 문장", result)
        source = '[절](Guide.md#설명)\n'
        with self.assertRaisesRegex(wiki.TranslationError, "explicit HTML id"):
            wiki.translate_markdown(source, "docs/wiki/Home-ko.md", "en", {"docs/wiki/Home-ko.md": source, "docs/wiki/Guide.md": "# 설명"}, fake_translate)
        source = '[절](#설명)\n\n# 설명\n'
        with self.assertRaisesRegex(wiki.TranslationError, "explicit HTML id"):
            wiki.translate_markdown(source, "docs/wiki/Home-ko.md", "en", {"docs/wiki/Home-ko.md": source}, fake_translate)

    def test_invalid_placeholders_markup_new_numbers_and_truncation_fail(self):
        original = ["내용 ⟦NURI_000000⟧ 중간 ⟦NURI_000001⟧"]
        for text in ("Missing", "⟦NURI_000001⟧ ⟦NURI_000000⟧", "⟦NURI_000000⟧ ⟦NURI_000001⟧ 99",
                     "⟦NURI_000000⟧ ⟦NURI_000001⟧ <script>", "⟦NURI_000000⟧\n⟦NURI_000001⟧",
                     "# Added ⟦NURI_000000⟧ ⟦NURI_000001⟧", "- Added ⟦NURI_000000⟧ ⟦NURI_000001⟧",
                     "*Added* ⟦NURI_000000⟧ ⟦NURI_000001⟧", "한국어 ⟦NURI_000000⟧ ⟦NURI_000001⟧"):
            with self.subTest(text=text), self.assertRaises(wiki.TranslationError):
                wiki.validate_segments(original, [text])
        for finish in ("MAX_TOKENS", "SAFETY", "RECITATION", None):
            with self.subTest(finish=finish), self.assertRaises(wiki.TranslationError):
                wiki.parse_response(payload(["Translated"], finish), ["내용"])

    def test_response_requires_exact_unique_ids_nonblank_strings_and_json(self):
        good = payload(["One", "Two"])
        self.assertEqual(wiki.parse_response(good, ["첫째", "둘째"]), ["One", "Two"])
        for replacements in (
            [{"id": "s0000", "text": "One"}, {"id": "s0000", "text": "Two"}],
            [{"id": "s0000", "text": "One"}, {"id": "s0999", "text": "Two"}],
            [{"id": "s0000", "text": "One"}, {"id": "s0001", "text": ""}],
        ):
            bad = deepcopy(good)
            bad["candidates"][0]["content"]["parts"][0]["text"] = json.dumps({"translations": replacements})
            with self.assertRaises(wiki.TranslationError):
                wiki.parse_response(bad, ["첫째", "둘째"])
        malformed = deepcopy(good)
        malformed["candidates"][0]["content"]["parts"][0]["text"] = "not JSON"
        with self.assertRaises(wiki.TranslationError):
            wiki.parse_response(malformed, ["첫째", "둘째"])

    def test_svg_batches_texts_and_preserves_geometry(self):
        source = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="700" aria-label="전체 구조"><rect x="20" y="30" width="250" height="90" fill="#fff"/><text x="40" y="55">하루 25회</text><text x="40" y="75"><tspan>요청 결과</tspan> 꼬리 설명</text></svg>'
        translate = Mock(side_effect=fake_translate)
        result = wiki.translate_svg(source, "docs/assets/architecture-ko.svg", "en", {}, translate)
        self.assertEqual(translate.call_count, 1)
        before, after = ET.fromstring(source), ET.fromstring(result)
        self.assertEqual(before.attrib["width"], after.attrib["width"])
        self.assertEqual(before.attrib["height"], after.attrib["height"])
        self.assertEqual(list(before)[0].attrib, list(after)[0].attrib)
        self.assertNotEqual(before.attrib["aria-label"], after.attrib["aria-label"])
        self.assertIn("25", result)
        self.assertNotIn("하루", result)
        self.assertNotIn("꼬리", result)

    def test_http_and_network_errors_are_redacted_and_not_retried(self):
        for error in (HTTPError("https://host/PRIVATE", 429, "SECRET-DATA", {}, None), URLError("SECRET-DATA")):
            translator = wiki.GeminiTranslator("SECRET-KEY")
            translator.opener = Mock()
            translator.opener.open.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(wiki.TranslationError) as caught:
                translator(["내용"], "en")
            self.assertNotIn("SECRET", str(caught.exception))
            self.assertEqual(translator.opener.open.call_count, 1)

    def test_missing_key_fails_safely_without_writing(self):
        before = self.snapshot()
        stderr = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stderr(stderr):
            self.assertEqual(wiki.main(["--root", str(self.root)]), 1)
        self.assertIn("GEMINI_API_KEY is required", stderr.getvalue())
        self.assertEqual(before, self.snapshot())

    def test_seed_missing_target_and_unclosed_code_fail_without_writes(self):
        (self.root / "docs/wiki/Home-en.md").unlink()
        before = self.snapshot()
        with self.assertRaises(wiki.TranslationError):
            wiki.synchronize(self.root, seed=True)
        self.assertEqual(before, self.snapshot())
        with self.assertRaisesRegex(wiki.TranslationError, "Unclosed"):
            wiki.protect("```python\n한국어", "docs/wiki/Home-ko.md", "en", {})

    def test_state_cannot_target_files_outside_managed_documentation(self):
        self.write(wiki.STATE_PATH, json.dumps({"version": 1, "sources": {"../../private.md": {"targets": {}}}}))
        with self.assertRaises(wiki.TranslationError):
            wiki.synchronize(self.root, check=True)
        with self.assertRaises(wiki.TranslationError):
            wiki.safe_path(self.root, "../outside.md")


if __name__ == "__main__":
    unittest.main()
