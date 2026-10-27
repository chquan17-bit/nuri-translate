"""Only the selected message's human text reaches the translator."""

import unittest

from nuri.models import UserError
from nuri.selected_message import MENTIONS_ONLY, NO_SELECTED_TEXT, selected_message_text


class SelectedMessageTests(unittest.TestCase):
    def test_plaintext_is_preserved(self):
        text = "First line.\n  Second line with indentation."
        self.assertEqual(selected_message_text({"content": text}), text)

    def test_embed_only_reads_title_description_and_fields(self):
        message = {"content": "", "embeds": [{"title": "Release update",
            "description": "The new version is available.", "fields": [
                {"name": "Changes", "value": "Faster startup."}]}]}
        self.assertEqual(selected_message_text(message),
                         "Release update\n\nThe new version is available.\n\nChanges\n\nFaster startup.")

    def test_role_ping_plus_embed_uses_actual_visible_text(self):
        message = {"content": "<@&1224161131703042068>",
                   "embeds": [{"description": "We rolled out the update."}]}
        self.assertEqual(selected_message_text(message), "We rolled out the update.")

    def test_mentions_do_not_remove_surrounding_prose_or_invent_names(self):
        text = selected_message_text({"content": "Hello<@123>team! <@&456> Join <#789>."})
        self.assertIn("Hello team!", text)
        self.assertIn("Join", text)
        self.assertNotIn("<@", text)
        self.assertNotIn("<#", text)

    def test_only_mentions_reject_instead_of_translating_ids(self):
        for content in ("<@&1224161131703042068>", "<@123> <@!456> <#789>",
                        "**<@&123>**", "@everyone @here"):
            with self.subTest(content=content), self.assertRaises(UserError) as error:
                selected_message_text({"content": content})
            self.assertEqual(str(error.exception), MENTIONS_ONLY)

    def test_multiple_embeds_deduplicate_exact_text_and_ignore_nontext_metadata(self):
        message = {"content": "Repeated description.", "embeds": [
            {"title": "News", "description": "Repeated description.",
             "url": "https://never-fetch.example/page",
             "footer": {"text": "Do not include footer"},
             "author": {"name": "Do not include author"},
             "image": {"url": "https://never-fetch.example/private.png"}},
            {"title": "News", "description": "Second item.",
             "fields": [{"name": "Detail", "value": "Useful text"}]}],
            "attachments": [{"filename": "Do not include attachment.txt"}]}
        self.assertEqual(selected_message_text(message),
                         "Repeated description.\n\nNews\n\nSecond item.\n\nDetail\n\nUseful text")

    def test_missing_text_or_malformed_fields_cannot_invent_source(self):
        for message in ({}, None, {"embeds": [{"description": None, "fields": [42]}]},
                        {"content": "", "embeds": "not a list"},
                        {"embeds": [{"image": {"url": "https://example.org/image.png"}}]}):
            with self.subTest(message=message), self.assertRaises(UserError) as error:
                selected_message_text(message)
            self.assertEqual(str(error.exception), NO_SELECTED_TEXT)


if __name__ == "__main__":
    unittest.main()
