"""Offline contracts for publishing multilingual documentation, never the bot."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts import sync_wiki


class WikiExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        self.source = self.root / "docs/wiki"
        self.source.mkdir(parents=True)
        self.assets = self.root / "docs/assets"
        self.assets.mkdir()
        self.wiki = Path(self.temporary.name) / "wiki"
        (self.wiki / ".git").mkdir(parents=True)
        for name in (*sync_wiki.SHARED, "Home-ko.md", "Home-en.md", "Home-zh-CN.md",
                     "Guide.md", "Guide-en.md", "Guide-zh-CN.md"):
            (self.source / name).write_text("# Title\n", encoding="utf-8")

    def test_links_anchors_images_references_and_code_examples(self):
        (self.assets / "diagram-ko.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "README.md").write_text("readme", encoding="utf-8")
        text = ('[Guide](Guide.md#section) ![Diagram](../assets/diagram-ko.svg)\n'
                '[Readme](../../README.md)\n[`Home`](Home-ko.md)\n[reference]: Guide-en.md "Title"\n'
                '`[example](missing.md)`\n\n    [example](missing.md)\n'
                '```md\n[example](absent.md)\n```\n')
        assets = set()
        output = sync_wiki.rewrite_markdown(text, self.source / "Home.md", self.root,
                                            "owner/repo", assets)
        self.assertIn("https://github.com/owner/repo/wiki/Guide#section", output)
        self.assertIn("https://raw.githubusercontent.com/wiki/owner/repo/assets/diagram-ko.png", output)
        self.assertIn('https://github.com/owner/repo/wiki/Guide-en "Title"', output)
        self.assertIn("blob/main/README.md", output)
        self.assertIn("[`Home`](https://github.com/owner/repo/wiki/Home-ko)", output)
        self.assertIn("`[example](missing.md)`", output)
        self.assertIn("    [example](missing.md)", output)
        self.assertIn("[example](absent.md)", output)
        self.assertEqual(assets, {(self.assets / "diagram-ko.svg").resolve()})

    def test_missing_language_or_broken_link_fails(self):
        (self.source / "Guide-en.md").unlink()
        with self.assertRaisesRegex(ValueError, "Missing language"):
            sync_wiki.prepare(self.root)
        (self.source / "Guide-en.md").write_text("[bad](unknown.md)", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Missing or private"):
            sync_wiki.prepare(self.root)

    def test_external_links_unchanged_and_private_or_escape_links_rejected(self):
        assets = set()
        for link in ("https://example.com/page#x", "mailto:hello@example.com", "#section"):
            self.assertEqual(sync_wiki.rewrite_url(link, self.source / "Home.md", self.root,
                                                  "owner/repo", assets), link)
        (self.root / ".state").mkdir()
        (self.root / ".state/private.md").write_text("private", encoding="utf-8")
        for link in ("../../../outside.md", "../../.state/private.md", "javascript:alert"):
            with self.subTest(link=link), self.assertRaises(ValueError):
                sync_wiki.rewrite_url(link, self.source / "Home.md", self.root, "owner/repo", assets)

    def test_managed_deletion_preserves_user_files_and_second_export_is_identical(self):
        sync_wiki.publish_files(self.root, self.wiki)
        (self.wiki / "Notes.md").write_text("User notes", encoding="utf-8")
        for name in ("Guide.md", "Guide-en.md", "Guide-zh-CN.md"):
            (self.source / name).unlink()
        sync_wiki.publish_files(self.root, self.wiki)
        self.assertFalse((self.wiki / "Guide.md").exists())
        self.assertEqual((self.wiki / "Notes.md").read_text(), "User notes")
        before = {p.name: p.read_bytes() for p in self.wiki.iterdir() if p.is_file()}
        sync_wiki.publish_files(self.root, self.wiki)
        after = {p.name: p.read_bytes() for p in self.wiki.iterdir() if p.is_file()}
        self.assertEqual(before, after)

    def test_render_failure_does_not_replace_published_pages(self):
        sync_wiki.publish_files(self.root, self.wiki)
        before = (self.wiki / "Guide.md").read_bytes()
        (self.assets / "diagram-ko.svg").write_text("<svg/>", encoding="utf-8")
        (self.source / "Guide.md").write_text("# Changed\n![x](../assets/diagram-ko.svg)", encoding="utf-8")
        def failed_renderer(*args):
            raise ValueError("Rendering failed")
        with self.assertRaisesRegex(ValueError, "Rendering failed"):
            sync_wiki.publish_files(self.root, self.wiki, renderer=failed_renderer)
        self.assertEqual((self.wiki / "Guide.md").read_bytes(), before)

    def test_manifest_cannot_remove_git_or_paths_outside_checkout(self):
        for bad in (".git/config", "../outside.md", "assets/../../secret", "/outside.md"):
            (self.wiki / sync_wiki.MANIFEST).write_text(json.dumps({"files": [bad]}), encoding="utf-8")
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, "Invalid managed"):
                sync_wiki.publish_files(self.root, self.wiki)

    def test_symlinked_asset_or_manifest_is_rejected(self):
        target = self.root / "outside.svg"
        target.write_text("<svg/>", encoding="utf-8")
        link = self.assets / "diagram-ko.svg"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Symlinks unavailable on this platform")
        (self.source / "Guide.md").write_text("![x](../assets/diagram-ko.svg)", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            sync_wiki.prepare(self.root)
        link.unlink()
        (self.source / "Guide.md").write_text("# Guide", encoding="utf-8")
        manifest_target = self.root / "outside.json"
        manifest_target.write_text('{"files": []}', encoding="utf-8")
        (self.wiki / sync_wiki.MANIFEST).symlink_to(manifest_target)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            sync_wiki.publish_files(self.root, self.wiki)


if __name__ == "__main__":
    unittest.main()
