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
    category_hierarchy_path,
    category_path,
    sanitize_filename,
    scan_existing_mods,
)


def parse_single_mod(
    mod_id,
    custom_path=None,
    preserve_time=True,
    skip_existing=False,
    category_folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
    section="mods",
):
    model = api.content_model(section)
    mod = api.get_mod_record(mod_id, section=section)
    game_name = sanitize_filename(mod["_aGame"]["_sName"])
    category_id, category_name = category_from_mod(mod)
    if custom_path:
        path = os.path.join(custom_path, f"{model.lower()}_{mod_id}")
    elif category_id is not None:
        path = category_path(
            DEFAULT_OUTPUT_ROOT,
            game_name,
            category_id,
            category_name,
            category_folder_format,
            hierarchy=api.get_category_hierarchy(category_id, section=section),
            section=section,
        )
    else:
        path = os.path.join(
            DEFAULT_OUTPUT_ROOT, section, game_name, "_individual"
        )
    os.makedirs(path, exist_ok=True)

    existing_ids = scan_existing_mods(path, section=section)
    if skip_existing and mod_id in existing_ids:
        print(
            f"\nSkipping already downloaded submission {mod_id}: "
            f"{existing_ids[mod_id]}"
        )
        return
    print(f"\n----- {mod['_sName']} ({mod_id}) ------")
    download_mod(
        mod,
        path,
        category_id or mod_id,
        preserve_time=preserve_time,
        used_folders=set(existing_ids.values()),
        existing_folder=existing_ids.get(mod_id),
        section=section,
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
    section="mods",
):
    api.content_model(section)
    if custom_path and section != "mods":
        custom_path = os.path.join(custom_path, section)
    if source_type == "category":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        hierarchy = api.get_category_hierarchy(source_id, section=section)
        parent = custom_path or os.path.join(
            DEFAULT_OUTPUT_ROOT, section, game_name
        )
        return category_hierarchy_path(
            parent, hierarchy, category_folder_format,
            extra_legacy_labels=(f"category_{source_id}",) if custom_path else (),
        )

    if source_type == "submitter":
        submitter = sanitize_filename(
            mods[0]["_aSubmitter"]["_sName"]
        )
        if custom_path:
            parent = custom_path
            legacy_labels = (f"submitter_{source_id}",)
        else:
            parent = os.path.join(
                DEFAULT_OUTPUT_ROOT, section, "_submitters"
            )
            legacy_labels = (f"{submitter}_{source_id}",)

        path = os.path.join(parent, submitter)
        if not os.path.exists(path):
            legacy_paths = [
                os.path.join(parent, label)
                for label in legacy_labels
                if os.path.isdir(os.path.join(parent, label))
            ]
            if len(legacy_paths) == 1:
                os.rename(legacy_paths[0], path)
                print(
                    f"Renamed submitter folder: "
                    f"{legacy_paths[0]} -> {path}"
                )
        return path

    if source_type == "game":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        path = os.path.join(DEFAULT_OUTPUT_ROOT, section, game_name)
    if custom_path:
        return os.path.join(custom_path, f"{source_type}_{source_id}")
    return path


def _describe_source(source_id, source_type, mods, mod_count, num_pages):
    if source_type == "category":
        print(
            f"\nThis category ({source_id}) has {mod_count} submissions "
            f"in {num_pages} pages."
        )
    elif source_type == "game":
        game_name = sanitize_filename(mods[0]["_aGame"]["_sName"])
        print(
            f"\nGame '{game_name}' ({source_id}) has {mod_count} submissions "
            f"in {num_pages} pages."
        )
    else:
        submitter = sanitize_filename(
            mods[0]["_aSubmitter"]["_sName"]
        )
        print(
            f"\nSubmitter '{submitter}' ({source_id}) has {mod_count} submissions "
            f"in {num_pages} pages."
        )


def parse_mods(
    source_id,
    source_type="category",
    custom_path=None,
    preserve_time=True,
    sort=None,
    skip_existing=False,
    delay=2.0,
    category_folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
    section="mods",
    direct_category_only=False,
):
    if direct_category_only and source_type != "category":
        raise ValueError("--direct-category-only requires a category source")
    parameters = _index_parameters(source_id, source_type, sort)
    index = api.get_mod_index(parameters, section=section)
    mod_count = index["_aMetadata"]["_nRecordCount"]
    num_pages = math.ceil(mod_count / 50)
    if mod_count == 0:
        print(
            f"\nNo submissions found for {source_type} ID {source_id}. Skipping."
        )
        return

    mods = index["_aRecords"]
    if direct_category_only:
        print("Scanning category pages to count directly assigned submissions...")
        direct_mods = []
        for page in range(1, num_pages + 1):
            print(f"Scanning page {page}/{num_pages}")
            if page > 1:
                parameters["_nPage"] = page
                mods = api.get_mod_index(parameters, section=section)["_aRecords"]
            for mod in mods:
                assigned_id, _ = category_from_mod(mod)
                if assigned_id is None:
                    detail = api.get_mod_record(mod["_idRow"], section=section)
                    assigned_id, _ = category_from_mod(detail)
                    if assigned_id is None:
                        raise RuntimeError(
                            f"Could not determine category for submission {mod['_idRow']}"
                        )
                if assigned_id == source_id:
                    direct_mods.append(mod)
            if page < num_pages and delay > 0:
                time.sleep(min(delay, 1.0))
        mods = direct_mods
        mod_count = len(mods)
        print(
            f"Found {mod_count} submissions assigned directly to category {source_id}."
        )
        if not mods:
            return
    else:
        _describe_source(source_id, source_type, mods, mod_count, num_pages)
    path = _output_path(
        source_id,
        source_type,
        mods,
        custom_path,
        category_folder_format,
        section=section,
    )
    os.makedirs(path, exist_ok=True)

    existing_ids = scan_existing_mods(path, section=section)
    used_folders = set(existing_ids.values())

    def process_mod(mod, current):
        mod_id = mod["_idRow"]
        print(f"\n----- {mod['_sName']} ({current}/{mod_count}) ------")
        if skip_existing and mod_id in existing_ids:
            print(
                f"Skipping already downloaded submission {mod_id}: "
                f"{existing_ids[mod_id]}"
            )
            return
        completed_folder = download_mod(
            mod,
            path,
            source_id,
            preserve_time=preserve_time,
            used_folders=used_folders,
            existing_folder=existing_ids.get(mod_id),
            section=section,
        )
        if completed_folder:
            existing_ids[mod_id] = completed_folder
        if delay > 0:
            time.sleep(delay)

    if direct_category_only:
        for current, mod in enumerate(mods, 1):
            process_mod(mod, current)
        return

    current = 1
    for page in range(1, num_pages + 1):
        if num_pages > 1:
            print(f"Page {page}/{num_pages}")
        if page > 1:
            parameters["_nPage"] = page
            mods = api.get_mod_index(parameters, section=section)["_aRecords"]
        for mod in mods:
            process_mod(mod, current)
            current += 1
        if page < num_pages and delay > 0:
            time.sleep(min(delay, 1.0))
