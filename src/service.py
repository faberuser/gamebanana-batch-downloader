"""High-level orchestration for individual and batch downloads."""

import math
import os
import time

from . import api
from .config import (
    DEFAULT_CATEGORY_FOLDER_FORMAT,
    DEFAULT_OUTPUT_ROOT,
    SORT_ALIASES,
)
from .downloads import download_mod
from .paths import (
    category_from_mod,
    category_path,
    migrate_category_path,
    sanitize_filename,
    scan_existing_mods,
    write_mod_id_marker,
)


def parse_single_mod(
    mod_id,
    custom_path=None,
    download_metadata=False,
    preserve_time=True,
    skip_existing=False,
    category_folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
):
    mod = api.get_mod_record(mod_id)
    game_name = sanitize_filename(mod["_aGame"]["_sName"])
    category_id, category_name = category_from_mod(mod)
    if custom_path:
        path = os.path.join(custom_path, f"mod_{mod_id}")
    elif category_id is not None:
        path = category_path(
            DEFAULT_OUTPUT_ROOT,
            game_name,
            category_id,
            category_name,
            category_folder_format,
        )
    else:
        path = os.path.join(
            DEFAULT_OUTPUT_ROOT, "mods", game_name, "_individual"
        )
    os.makedirs(path, exist_ok=True)

    existing_ids = scan_existing_mods(path)
    if skip_existing and mod_id in existing_ids:
        print(
            f"\nSkipping already downloaded mod {mod_id}: "
            f"{existing_ids[mod_id]}"
        )
        return
    print(f"\n----- {mod['_sName']} ({mod_id}) ------")
    download_mod(
        mod,
        path,
        category_id or mod_id,
        download_metadata,
        preserve_time,
        used_folders=set(existing_ids.values()),
        existing_folder=existing_ids.get(mod_id),
    )


def _index_parameters(source_id, source_type, sort):
    parameters = {"_nPage": 1, "_nPerpage": 50}
    filters = {
        "category": "Generic_Category",
        "game": "Generic_Game",
        "submitter": "Generic_Submitter",
    }
    if source_type in filters:
        parameters[f"_aFilters[{filters[source_type]}]"] = {source_id}
    if sort == "featured":
        parameters["_aFilters[Generic_WasFeatured]"] = 1
    elif sort:
        parameters["_sSort"] = SORT_ALIASES.get(sort, sort)
    return parameters


def _output_path(
    source_id,
    source_type,
    mods,
    custom_path,
    category_folder_format,
):
    if source_type == "category":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        category_name = api.get_category_name(source_id, mods[0])
        path = category_path(
            DEFAULT_OUTPUT_ROOT,
            game_name,
            source_id,
            category_name,
            category_folder_format,
        )
        if custom_path:
            path = migrate_category_path(
                custom_path,
                source_id,
                category_name,
                category_folder_format,
                extra_legacy_labels=(f"category_{source_id}",),
            )
        return path

    if source_type == "game":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        path = os.path.join(DEFAULT_OUTPUT_ROOT, "mods", game_name)
    else:
        submitter = sanitize_filename(
            mods[0]["_aSubmitter"]["_sName"]
        )
        path = os.path.join(
            DEFAULT_OUTPUT_ROOT,
            "mods",
            "_submitters",
            f"{submitter}_{source_id}",
        )
    if custom_path:
        return os.path.join(custom_path, f"{source_type}_{source_id}")
    return path


def _describe_source(source_id, source_type, mods, mod_count, num_pages):
    if source_type == "category":
        print(
            f"\nThis category ({source_id}) has {mod_count} mods "
            f"in {num_pages} pages."
        )
    elif source_type == "game":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        print(
            f"\nGame '{game_name}' ({source_id}) has {mod_count} mods "
            f"in {num_pages} pages."
        )
    else:
        submitter = sanitize_filename(
            mods[0]["_aSubmitter"]["_sName"]
        )
        print(
            f"\nSubmitter '{submitter}' ({source_id}) has {mod_count} mods "
            f"in {num_pages} pages."
        )


def parse_mods(
    source_id,
    source_type="category",
    custom_path=None,
    download_metadata=False,
    preserve_time=True,
    sort=None,
    skip_existing=False,
    delay=2.0,
    category_folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
):
    parameters = _index_parameters(source_id, source_type, sort)
    index = api.get_mod_index(parameters)
    mod_count = index["_aMetadata"]["_nRecordCount"]
    num_pages = math.ceil(mod_count / 50)
    if mod_count == 0:
        print(
            f"\nNo mods found for {source_type} ID {source_id}. Skipping."
        )
        return

    mods = index["_aRecords"]
    _describe_source(
        source_id, source_type, mods, mod_count, num_pages
    )
    path = _output_path(
        source_id,
        source_type,
        mods,
        custom_path,
        category_folder_format,
    )
    os.makedirs(path, exist_ok=True)

    existing_ids = scan_existing_mods(path)
    used_folders = set(existing_ids.values())
    legacy_skips = set()

    def process_mod(mod, current):
        mod_id = mod["_idRow"]
        legacy_folder = os.path.join(
            path, sanitize_filename(mod["_sName"])
        )
        print(f"\n----- {mod['_sName']} ({current}/{mod_count}) ------")
        if skip_existing and mod_id in existing_ids:
            print(
                f"Skipping already downloaded mod {mod_id}: "
                f"{existing_ids[mod_id]}"
            )
            return
        if (
            skip_existing
            and os.path.isdir(legacy_folder)
            and legacy_folder not in legacy_skips
        ):
            print(f"Skipping legacy existing folder: {legacy_folder}")
            legacy_skips.add(legacy_folder)
            try:
                write_mod_id_marker(legacy_folder, mod_id)
                existing_ids[mod_id] = legacy_folder
                used_folders.add(legacy_folder)
            except OSError as error:
                print(f"Could not add resume marker: {error}")
            return

        completed_folder = download_mod(
            mod,
            path,
            source_id,
            download_metadata,
            preserve_time,
            used_folders,
            existing_folder=existing_ids.get(mod_id),
        )
        if completed_folder:
            existing_ids[mod_id] = completed_folder
        if delay > 0:
            time.sleep(delay)

    current = 1
    for page in range(1, num_pages + 1):
        if num_pages > 1:
            print(f"Page {page}/{num_pages}")
        if page > 1:
            parameters["_nPage"] = page
            mods = api.get_mod_index(parameters)["_aRecords"]
        for mod in mods:
            process_mod(mod, current)
            current += 1
        if page < num_pages and delay > 0:
            time.sleep(min(delay, 1.0))
