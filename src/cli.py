"""Command-line interface for GameBanana Downloader."""

import argparse
import os

from . import api, service, state
from .config import DEFAULT_CATEGORY_FOLDER_FORMAT, SORT_ALIASES
from .paths import format_category_folder


def category_folder_format(value):
    try:
        format_category_folder(7559, "Ness", value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gamebanana",
        description="Download GameBanana mods, categories, games, or submitters.",
    )
    parser.add_argument("--path", help="Custom path to save mods")
    parser.add_argument(
        "--sort",
        choices=list(SORT_ALIASES) + ["featured"],
        help="Download priority/order (category URL _sSort is also honored)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip locally downloaded mods before requesting their details/files",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Delay between mods (default: 2; increase if rate limited)",
    )
    parser.add_argument(
        "--category-folder-format",
        type=category_folder_format,
        default=DEFAULT_CATEGORY_FOLDER_FORMAT,
        metavar="FORMAT",
        help=(
            "Category folder template using {id} and {name} "
            f"(default: '{DEFAULT_CATEGORY_FOLDER_FORMAT}')"
        ),
    )
    parser.add_argument(
        "source",
        nargs="+",
        help="Mod, Category, Game, or Submitter URL or ID (auto-detected)",
    )
    return parser


def write_failure_report(output_root):
    if not state.failed:
        return None

    report_path = os.path.join(output_root, "failed.txt")
    with open(report_path, "a", encoding="utf-8") as report:
        report.write("Failed to download the following mods:\n\n")
        for name, url, images, files in state.failed:
            report.write(f"{name}: {url}\n")
            if images:
                report.write("\nImages:\n")
                report.writelines(f"{image}\n" for image in images)
            if files:
                report.write("\nFiles:\n")
                report.writelines(f"{file_name}\n" for file_name in files)
            report.write("\n\n")
    return report_path


def main(argv=None):
    parser = build_parser()
    if hasattr(parser, "parse_intermixed_args"):
        args = parser.parse_intermixed_args(argv)
    else:
        args = parser.parse_args(argv)

    state.failed.clear()

    for source in args.source:
        source_type, source_id, url_sort = api.detect_source_type(source)
        type_label = {
            "category": "Category",
            "game": "Game",
            "submitter": "Submitter",
            "mod": "Mod",
        }.get(source_type, "Category")
        print(f"\nDetected: {type_label} ID = {source_id}")

        if source_type == "mod":
            service.parse_single_mod(
                source_id,
                custom_path=args.path,
                skip_existing=args.skip_existing,
                category_folder_format=args.category_folder_format,
            )
        else:
            selected_sort = args.sort or url_sort
            if selected_sort:
                print(f"Sort: {selected_sort}")
            service.parse_mods(
                source_id,
                source_type=source_type,
                custom_path=args.path,
                sort=selected_sort,
                skip_existing=args.skip_existing,
                delay=args.delay,
                category_folder_format=args.category_folder_format,
            )

    output_root = os.path.abspath(args.path or os.getcwd())
    report_path = write_failure_report(output_root)
    if report_path:
        print(f"\nFailure report: {report_path}")
    print("\ndone")
