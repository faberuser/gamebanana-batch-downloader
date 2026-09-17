import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from gamebanana import api, cli, downloads, metadata, paths, service, state
from gamebanana.config import CONTENT_MODELS, FILE_SECTIONS


def response(data):
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps(data).encode()
    return result


def submission(section, ident=123):
    return {
        "_idRow": ident,
        "_sName": "Example",
        "_sProfileUrl": f"https://gamebanana.com/{section}/{ident}",
        "_aGame": {"_idRow": 5892, "_sName": "Sonic Adventure DX"},
        "_aCategory": {"_sName": "Other/Misc", "_idRow": 30},
        "_aPreviewMedia": {"_aMetadata": {"_sSnippet": "Example text"}},
        "_sText": "Example text",
        "_sRawCode": "example code",
    }


class SectionTests(unittest.TestCase):
    def tearDown(self):
        state.failed.clear()

    def test_all_sections_keep_scope_id_and_sort(self):
        with patch.object(api.session, "get", side_effect=AssertionError("network")):
            for section in CONTENT_MODELS:
                for path, scope in (("123", "mod"), ("cats/123", "category"), ("games/123", "game")):
                    with self.subTest(section=section, scope=scope):
                        self.assertEqual(
                            api.detect_source(f"https://gamebanana.com/{section}/{path}/?_sSort=Generic_Oldest"),
                            (scope, 123, "Generic_Oldest", section),
                        )
            self.assertEqual(api.detect_source("https://gamebanana.com/games/5892"), ("game", 5892, None, "mods"))
            self.assertEqual(api.detect_source("https://gamebanana.com/members/123"), ("submitter", 123, None, "mods"))

    def test_unsupported_routes_are_not_treated_as_mod_categories(self):
        for url in (
            "https://gamebanana.com/unknown/games/5892",
            "https://gamebanana.com/unknown/123",
            "https://gamebanana.com/sounds/123/456",
            "https://example.com/sounds/123",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                api.detect_source(url)
        with self.assertRaisesRegex(ValueError, "retain non-Mod"):
            api.detect_source_type("https://gamebanana.com/sounds/123")

    def test_redirect_retains_resolved_section(self):
        redirected = response({})
        redirected.url = "https://gamebanana.com/sounds/123?_sSort=Generic_Oldest"
        with patch.object(api.session, "get", return_value=redirected):
            self.assertEqual(api.detect_source("https://gamebanana.com/short-link"), ("mod", 123, "Generic_Oldest", "sounds"))

    def test_cli_routes_individual_category_and_game_section(self):
        for section in CONTENT_MODELS:
            with (
                self.subTest(section=section),
                patch.object(service, "parse_single_mod") as single,
                patch.object(service, "parse_mods") as batch,
            ):
                cli.main([
                    f"https://gamebanana.com/{section}/123",
                    f"https://gamebanana.com/{section}/cats/30",
                    f"https://gamebanana.com/{section}/games/5892",
                ])
                self.assertEqual(single.call_args.kwargs["section"], section)
                self.assertEqual([call.kwargs["source_type"] for call in batch.call_args_list], ["category", "game"])
                self.assertTrue(all(call.kwargs["section"] == section for call in batch.call_args_list))

    def test_detail_file_and_comment_requests_use_section_model(self):
        for section, model in CONTENT_MODELS.items():
            with self.subTest(section=section):
                with patch.object(api.session, "get", return_value=response(submission(section))) as get:
                    api.get_mod_record(123, section=section)
                    expected = f"https://gamebanana.com/apiv11/{model}/123"
                    if section != "mods":
                        expected += "/ProfilePage"
                    self.assertEqual(get.call_args.args[0], expected)
                with patch.object(api.session, "get", return_value=response({"_aFiles": []})) as get:
                    self.assertEqual(api.get_files(123, section=section), [])
                    if section in FILE_SECTIONS:
                        self.assertEqual(get.call_args.args[0], f"https://gamebanana.com/apiv11/{model}/123")
                    else:
                        get.assert_not_called()
                with patch.object(api, "request_all_records", side_effect=[
                    [{"_idRow": 90, "_nReplyCount": 1}], [{"_idRow": 91}],
                ]) as get:
                    posts = api.get_posts_with_replies(123, section=section)
                    self.assertEqual(get.call_args_list[0].args[0], f"https://gamebanana.com/apiv11/{model}/123/Posts")
                    self.assertEqual(get.call_args_list[1].args[0], "https://gamebanana.com/apiv11/Post/90/Posts")
                    self.assertEqual(posts[0]["_aReplies"], [{"_idRow": 91}])

    def test_section_persists_across_batch_pages(self):
        for section, model in CONTENT_MODELS.items():
            with self.subTest(section=section), tempfile.TemporaryDirectory() as root:
                with (
                    patch.object(api.session, "get", side_effect=[
                        response({"_aMetadata": {"_nRecordCount": 51}, "_aRecords": [submission(section)]}),
                        response({"_aRecords": [submission(section, 124)]}),
                    ]) as get,
                    patch.object(service, "download_mod", return_value=None) as download,
                ):
                    service.parse_mods(5892, "game", custom_path=root, section=section, delay=0)
                self.assertEqual(get.call_count, 2)
                for call in get.call_args_list:
                    self.assertEqual(call.args[0], f"https://gamebanana.com/apiv11/{model}/Index")
                    self.assertEqual(call.kwargs["params"]["_aFilters[Generic_Game]"], {5892})
                for call in download.call_args_list:
                    self.assertEqual(call.kwargs["section"], section)
                    parent = Path(root) if section == "mods" else Path(root) / section
                    self.assertEqual(Path(call.args[1]), parent / "game_5892")

    def test_sound_download_without_images_uses_sound_files_and_metadata(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch.object(api, "get_files", return_value=[{"name": "sound.zip", "url": "https://example.com/sound.zip"}]) as files,
            patch.object(downloads, "download_file", return_value="success") as download,
            patch.object(metadata, "write_mod_metadata") as write,
        ):
            self.assertIsNotNone(downloads.download_mod(submission("sounds"), root, 30, section="sounds"))
            files.assert_called_once_with(123, section="sounds")
            self.assertEqual(download.call_args.args[0], "https://example.com/sound.zip")
            self.assertEqual(write.call_args.kwargs["section"], "sounds")

    def test_individual_sound_uses_nested_sound_path_and_resumes(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch.object(service, "DEFAULT_OUTPUT_ROOT", root),
            patch.object(api, "get_mod_record", return_value=submission("sounds")) as record,
            patch.object(api, "get_category_hierarchy", return_value=[
                (20, "Music"), (30, "Other/Misc"),
            ]) as hierarchy,
            patch.object(service, "download_mod") as download,
        ):
            service.parse_single_mod(123, section="sounds")
            record.assert_called_once_with(123, section="sounds")
            hierarchy.assert_called_once_with(30, section="sounds")
            target = (
                Path(root) / "sounds" / "Sonic Adventure DX"
                / "Music" / "Other-Misc"
            )
            self.assertEqual(Path(download.call_args.args[1]), target)
            self.assertEqual(download.call_args.kwargs["section"], "sounds")
            completed = target / "Example"
            completed.mkdir()
            (completed / "metadata.json").write_text(json.dumps({
                "_section": "sounds", "_mod": {"_idRow": 123},
            }), encoding="utf-8")
            download.reset_mock()
            service.parse_single_mod(123, section="sounds", skip_existing=True)
            download.assert_not_called()

    def test_text_submission_archives_content_and_resumes_by_section(self):
        for section in ("tuts", "scripts", "projects", "concepts"):
            with (
                self.subTest(section=section),
                tempfile.TemporaryDirectory() as root,
                patch.object(api, "get_mod_metadata", return_value=submission(section)),
                patch.object(api, "get_posts_with_replies", return_value=[]),
            ):
                folder = downloads.download_mod(submission(section), root, 30, section=section)
                stored = json.loads((Path(folder) / "metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(stored["_section"], section)
                self.assertEqual(stored["_mod"]["_sText"], "Example text")
                self.assertEqual(stored["_mod"]["_sRawCode"], "example code")
                self.assertEqual(paths.scan_existing_mods(root, section=section), {123: folder})
                self.assertEqual(paths.scan_existing_mods(root, section="mods"), {})

    def test_sound_category_uses_sound_breadcrumbs_and_separate_folder(self):
        breadcrumb = {"itemListElement": [
            {"position": 1, "item": {"@id": "https://gamebanana.com/sounds/cats/20", "name": "Music"}},
            {"position": 2, "item": {"@id": "https://gamebanana.com/sounds/cats/30", "name": "Other/Misc"}},
        ]}
        page = response({})
        page._content = ('<script id="StructuredDataBreadcrumb">' + json.dumps(breadcrumb) + '</script>').encode()
        with tempfile.TemporaryDirectory() as root, patch.object(api.session, "get", return_value=page) as get:
            result = service._output_path(30, "category", [submission("sounds")], root, "{name}", section="sounds")
            get.assert_called_once_with("https://gamebanana.com/sounds/cats/30", timeout=30)
            self.assertEqual(Path(result), Path(root) / "sounds" / "Music" / "Other-Misc")

    def test_sound_failure_reports_sound_url(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch.object(api, "get_files", return_value=[{"name": "sound.zip", "url": "https://example.com/sound.zip"}]),
            patch.object(downloads, "download_file", return_value="failed"),
        ):
            self.assertIsNone(downloads.download_mod(submission("sounds"), root, 30, section="sounds"))
        self.assertEqual(state.failed[0][1], "https://gamebanana.com/sounds/123")

    def test_comment_json_with_php_warning_prefix(self):
        page = response({"_aRecords": [{"_idRow": 90}]})
        page._content = b'\nWarning: Undefined array key "images" in server.php on line 87\n' + page.content
        with patch.object(api.session, "get", return_value=page):
            self.assertEqual(api.request_all_records("https://gamebanana.com/apiv11/Tutorial/123/Posts"), [{"_idRow": 90}])
        page._content = b'<html>Error</html>'
        with (
            patch.object(api.session, "get", return_value=page),
            patch.object(api.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON.*Tutorial/123/Posts"):
                api.request_all_records("https://gamebanana.com/apiv11/Tutorial/123/Posts")


if __name__ == "__main__":
    unittest.main()
