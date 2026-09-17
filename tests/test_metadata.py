import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from gamebanana import api, metadata


def response(body):
    result = requests.Response()
    result.status_code = 200
    result._content = body.encode("utf-8")
    result.encoding = "utf-8"
    return result


def warning_response(data):
    return response(
        '\nWarning: Undefined array key "images" in server.php on line 87\n'
        + json.dumps(data)
    )


class MetadataTests(unittest.TestCase):
    def test_metadata_comments_and_replies_accept_warning_prefix(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch.object(api.session, "get", side_effect=[
                warning_response({"_idRow": 712621, "_sName": "Example"}),
                warning_response({"_aRecords": [
                    {"_idRow": 50, "_nReplyCount": 1},
                ]}),
                warning_response({"_aRecords": [{"_idRow": 51}]}),
            ]) as get,
        ):
            metadata.write_mod_metadata(712621, root, 1, preserve_time=False)
            saved = json.loads((Path(root) / "metadata.json").read_text())
            self.assertEqual(saved["_mod"]["_idRow"], 712621)
            self.assertEqual(
                saved["_comments"][0]["_aReplies"], [{"_idRow": 51}]
            )
            self.assertEqual(get.call_count, 3)

    def test_transient_empty_and_html_responses_are_retried(self):
        with (
            patch.object(api.session, "get", side_effect=[
                response("\n"), response("<html>Temporarily unavailable</html>"),
                response('{"_idRow": 712621}'),
            ]) as get,
            patch.object(api.time, "sleep") as sleep,
        ):
            result = api.get_mod_metadata(712621, ["_idRow"])
            self.assertEqual(result, {"_idRow": 712621})
            self.assertEqual(get.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_invalid_comment_response_does_not_write_completion_metadata(self):
        for body in (
            "", '<html>{"_aRecords": []}</html>',
            'Warning: server warning\n{"_aRecords": [',
        ):
            with (
                self.subTest(body=body),
                tempfile.TemporaryDirectory() as root,
                patch.object(api.session, "get", side_effect=[
                    response('{"_idRow": 712621}'),
                    response(body), response(body), response(body),
                ]) as get,
                patch.object(api.time, "sleep"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Mod/712621/Posts.*after 3 attempts"
                ):
                    metadata.write_mod_metadata(712621, root, 1)
                self.assertEqual(get.call_count, 4)
                self.assertFalse((Path(root) / "metadata.json").exists())
                self.assertFalse((Path(root) / "metadata.json.part").exists())

    def test_api_error_is_not_mistaken_for_empty_comments(self):
        with patch.object(api.session, "get", return_value=response(
            '{"_sErrorCode": "UNAVAILABLE"}'
        )) as get:
            with self.assertRaisesRegex(RuntimeError, "UNAVAILABLE"):
                api.get_posts_with_replies(712621)
            self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
