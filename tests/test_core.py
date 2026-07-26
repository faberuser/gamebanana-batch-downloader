import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import gamebanana.core as core
from gamebanana import api, downloads, service


class FakeResponse:
    def __init__(self, data, url="https://gamebanana.com/"):
        self._data = data
        self.url = url
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def mod_record(mod_id=123, name="Bart Simpson"):
    return {
        "_idRow": mod_id,
        "_sName": name,
        "_aGame": {"_sName": "Super Smash Bros. Ultimate"},
        "_aCategory": {
            "_sName": "Ness",
            "_sProfileUrl": "https://gamebanana.com/mods/cats/7559",
        },
        "_aRootCategory": {
            "_sName": "Skins",
            "_sProfileUrl": "https://gamebanana.com/mods/cats/12",
        },
        "_aPreviewMedia": {"_aImages": []},
        "_aSubmitter": {"_sName": "Author"},
    }


class CoreTests(unittest.TestCase):
    def test_detects_category_sort_without_network(self):
        result = core.detect_source_type(
            "https://gamebanana.com/mods/cats/5299"
            "?_sSort=Generic_MostDownloaded"
        )
        self.assertEqual(
            result, ("category", 5299, "Generic_MostDownloaded")
        )

    def test_detects_individual_mod_without_network(self):
        self.assertEqual(
            core.detect_source_type(
                "https://gamebanana.com/mods/497545"
            ),
            ("mod", 497545, None),
        )

    def test_category_name_comes_from_index_record(self):
        self.assertEqual(core.get_category_name(7559, mod_record()), "Ness")

    def test_category_folder_formats(self):
        expected = {
            "{name}": "Ness",
            "{id}": "7559",
            "{name} ({id})": "Ness (7559)",
            "{id} ({name})": "7559 (Ness)",
            "{id} - {name}": "7559 - Ness",
        }
        for template, folder_name in expected.items():
            with self.subTest(template=template):
                self.assertEqual(
                    core.format_category_folder(7559, "Ness", template),
                    folder_name,
                )

    def test_category_folder_format_rejects_unknown_placeholder(self):
        with self.assertRaisesRegex(ValueError, r"\{id\} and \{name\}"):
            core.format_category_folder(7559, "Ness", "{game}")

    def test_numeric_category_folder_is_migrated(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            legacy = (
                root / "mods" / "Super Smash Bros. Ultimate" / "7559"
            )
            legacy.mkdir(parents=True)

            result = core.category_path(
                str(root), "Super Smash Bros. Ultimate", 7559, "Ness"
            )

            expected = legacy.with_name("Ness")
            self.assertEqual(Path(result), expected)
            self.assertTrue(expected.is_dir())
            self.assertFalse(legacy.exists())

    def test_category_folder_is_migrated_between_formats(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            old_path = (
                root / "mods" / "Super Smash Bros. Ultimate" / "7559 (Ness)"
            )
            old_path.mkdir(parents=True)

            result = core.category_path(
                str(root),
                "Super Smash Bros. Ultimate",
                7559,
                "Ness",
                "{name} ({id})",
            )

            self.assertEqual(Path(result).name, "Ness (7559)")
            self.assertTrue(Path(result).is_dir())
            self.assertFalse(old_path.exists())

    def test_submitter_folder_drops_id_and_migrates_old_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            old_path = (
                root / "mods" / "_submitters" / "Author_123"
            )
            old_path.mkdir(parents=True)

            with patch.object(
                service, "DEFAULT_OUTPUT_ROOT", str(root)
            ):
                result = service._output_path(
                    123,
                    "submitter",
                    [mod_record()],
                    None,
                    "{name}",
                )

            expected = old_path.with_name("Author")
            self.assertEqual(Path(result), expected)
            self.assertTrue(expected.is_dir())
            self.assertFalse(old_path.exists())

    def test_skip_existing_avoids_per_mod_requests(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "category_7559" / "Bart Simpson"
            target.mkdir(parents=True)
            (target / "metadata.json").write_text(
                json.dumps({"_mod": {"_idRow": 123}}),
                encoding="utf-8",
            )
            calls = []

            class FakeSession:
                def get(self, url, params=None, **kwargs):
                    calls.append((url, dict(params or {})))
                    return FakeResponse({
                        "_aMetadata": {"_nRecordCount": 1},
                        "_aRecords": [mod_record()],
                    })

            def unexpected_detail_request(*args, **kwargs):
                raise AssertionError("skip-existing made a per-mod request")

            with (
                patch.object(api, "session", FakeSession()),
                patch.object(api, "get_files", unexpected_detail_request),
            ):
                core.parse_mods(
                    7559,
                    "category",
                    str(root),
                    sort="most-downloaded",
                    skip_existing=True,
                    delay=0,
                )

            self.assertEqual(len(calls), 1)
            self.assertEqual(
                calls[0][1]["_sSort"], "Generic_MostDownloaded"
            )

    def test_download_always_writes_metadata_after_assets_succeed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(api, "get_files", return_value=[]),
                patch.object(
                    downloads.metadata, "write_mod_metadata"
                ) as write_metadata,
            ):
                result = downloads.download_mod(
                    mod_record(),
                    temporary_directory,
                    7559,
                    preserve_time=False,
                )

            self.assertIsNotNone(result)
            write_metadata.assert_called_once()

    def test_failed_asset_does_not_create_completion_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(
                    api,
                    "get_files",
                    return_value=[{
                        "name": "mod.zip",
                        "url": "https://example.com/mod.zip",
                        "ts": None,
                    }],
                ),
                patch.object(downloads, "download_file", return_value="failed"),
                patch.object(
                    downloads.metadata, "write_mod_metadata"
                ) as write_metadata,
            ):
                result = downloads.download_mod(
                    mod_record(),
                    temporary_directory,
                    7559,
                    preserve_time=False,
                )

            self.assertIsNone(result)
            write_metadata.assert_not_called()


if __name__ == "__main__":
    unittest.main()
