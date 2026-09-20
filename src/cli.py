"""Command-line interface for GameBanana Downloader."""

import argparse
import os
from urllib.parse import urlparse

from . import api, service, state
from .config import CONTENT_MODELS, DEFAULT_CATEGORY_FOLDER_FORMAT, SORT_ALIASES
from .paths import format_category_folder


def category_folder_format(value):
    try:
        format_category_folder(7559, "Ness", value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return value


def section_list(value):
    sections = list(dict.fromkeys(part.strip() for part in value.split(",")))
    if not sections or any(section not in CONTENT_MODELS for section in sections):
        raise argparse.ArgumentTypeError(
            "Use comma-separated sections: " + ", ".join(CONTENT_MODELS)
        )
    return sections


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gamebanana",
        description="Archive GameBanana submissions, categories, or game sections.",
    )
    parser.add_argument("--path", help="Custom path to save submissions")
    parser.add_argument("--sections", type=section_list,
                        help="Whole-game sections to include, e.g. sounds,tuts")
    parser.add_argument("--exclude-sections", type=section_list, default=[],
                        help="Whole-game sections to exclude, e.g. wips,projects")
    parser.add_argument("--flat", action="store_true",
                        help="Keep game-section downloads flat instead of using category folders")
    parser.add_argument("--no-category-brackets", action="store_true",
                        help="Use plain subcategory folder names instead of [Name]")
    parser.add_argument(
        "--direct-category-only",
        action="store_true",
        help="Download only submissions assigned to this category, excluding subcategories",
    )
    parser.add_argument(
        "--sort",
        choices=list(SORT_ALIASES) + ["featured"],
        help="Download priority/order (category URL _sSort is also honored)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip locally downloaded submissions before requesting their details/files",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Delay between submissions (default: 2; increase if rate limited)",
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
        help="Submission, Category, Game, or Submitter URL; bare IDs use Mods",
    )
    return parser


def write_failure_report(output_root):
    if not state.failed:
        return None

    report_path = os.path.join(output_root, "failed.txt")
    with open(report_path, "a", encoding="utf-8") as report:
        report.write("Failed to download the following submissions:\n\n")
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
        try:
            source_type, source_id, url_sort, section = api.detect_source(source)
        except ValueError as error:
            parser.error(str(error))
        if args.direct_category_only and source_type != "category":
            parser.error("--direct-category-only requires a category URL or ID")
        whole_game = source_type == "game" and (
            source.isdigit() or urlparse(source).path.strip("/").startswith("games/")
        )
        if (args.sections is not None or args.exclude_sections) and not whole_game:
            parser.error("Section selection requires a whole-game /games/ID URL or game ID")
        if args.flat and source_type != "game":
            parser.error("--flat requires a game URL")
        sections = args.sections if args.sections is not None else list(CONTENT_MODELS)
        selected_sections = [s for s in sections if s not in args.exclude_sections]
        if whole_game and not selected_sections:
            parser.error("No sections remain after exclusions")
        type_label = {
            "category": "Category",
            "game": "Game",
            "submitter": "Submitter",
            "mod": api.content_model(section),
        }.get(source_type, "Category")
        print(f"\nDetected: {type_label} ID = {source_id} (section: {section})")

        if source_type == "mod":
            service.parse_single_mod(
                source_id,
                custom_path=args.path,
                skip_existing=args.skip_existing,
                category_folder_format=args.category_folder_format,
                section=section,
                bracket_subcategories=not args.no_category_brackets,
            )
        else:
            selected_sort = args.sort or url_sort
            if selected_sort:
                print(f"Sort: {selected_sort}")
            for selected_section in selected_sections if whole_game else [section]:
                print(f"\nSection: {selected_section}")
                service.parse_mods(
                    source_id,
                    source_type=source_type,
                    custom_path=args.path,
                    sort=selected_sort,
                    skip_existing=args.skip_existing,
                    delay=args.delay,
                    direct_category_only=args.direct_category_only,
                    category_folder_format=args.category_folder_format,
                    section=selected_section,
                    organize_categories=not args.flat,
                    bracket_subcategories=not args.no_category_brackets,
                )

    output_root = os.path.abspath(args.path or os.getcwd())
    report_path = write_failure_report(output_root)
    if report_path:
        print(f"\nFailure report: {report_path}")
    print("\ndone")
