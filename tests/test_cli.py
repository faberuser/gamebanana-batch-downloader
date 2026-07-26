import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from gamebanana.cli import build_parser


class CliTests(unittest.TestCase):
    def test_category_name_is_the_default_folder_format(self):
        args = build_parser().parse_args(["7559"])

        self.assertEqual(args.category_folder_format, "{name}")

    def test_cli_parses_resume_and_sort_options(self):
        args = build_parser().parse_args([
            "--skip-existing",
            "--sort",
            "oldest",
            "https://gamebanana.com/mods/cats/5299",
        ])

        self.assertTrue(args.skip_existing)
        self.assertEqual(args.sort, "oldest")
        self.assertEqual(
            args.source, ["https://gamebanana.com/mods/cats/5299"]
        )

    def test_cli_parses_category_folder_format(self):
        args = build_parser().parse_args([
            "--category-folder-format",
            "{name} ({id})",
            "7559",
        ])

        self.assertEqual(args.category_folder_format, "{name} ({id})")


if __name__ == "__main__":
    unittest.main()
