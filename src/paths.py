"""Filesystem naming, timestamps, markers, and category paths."""

import json
import os
from string import Formatter
from urllib.parse import urlparse

from .config import (
    CATEGORY_FOLDER_FORMAT_EXAMPLES,
    DEFAULT_CATEGORY_FOLDER_FORMAT,
    MOD_ID_MARKER,
)


def sanitize_filename(name):
    for character in '\\/|:*?"<>':
        name = name.replace(character, "-")
    return name


def apply_timestamp(path, timestamp):
    if timestamp is None:
        return
    try:
        os.utime(path, (timestamp, timestamp))
    except Exception as error:
        print(f"Could not set file time for {path}: {error}")


def category_id_from_record(category):
    """Return the ID at the end of a category's profile URL."""
    if not isinstance(category, dict):
        return None
    profile_url = category.get("_sProfileUrl", "")
    try:
        return int(urlparse(profile_url).path.rstrip("/").split("/")[-1])
    except (TypeError, ValueError):
        return category.get("_idRow")


def category_from_mod(mod):
    """Return the deepest category ID and name present in a mod record."""
    for key in ("_aSubCategory", "_aRootCategory"):
        category = mod.get(key)
        category_id = category_id_from_record(category)
        if category_id is not None:
            return category_id, category.get("_sName")
    return None, None


def format_category_folder(
    category_id,
    category_name,
    folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
):
    """Render a safe category folder label from an ID/name template."""
    if not category_name:
        return str(category_id)
    try:
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(folder_format)
            if field_name is not None
        }
        if not fields or not fields.issubset({"id", "name"}):
            raise ValueError
        label = folder_format.format(
            id=category_id,
            name=sanitize_filename(category_name),
        )
    except (IndexError, KeyError, ValueError) as error:
        raise ValueError(
            "Category folder format may only use {id} and {name}"
        ) from error

    label = sanitize_filename(label).strip().rstrip(".")
    if not label:
        raise ValueError("Category folder format produced an empty name")
    return label


def migrate_category_path(
    parent,
    category_id,
    category_name,
    folder_format,
    extra_legacy_labels=(),
):
    label = format_category_folder(
        category_id, category_name, folder_format
    )
    new_path = os.path.join(parent, label)
    if os.path.exists(new_path) or not category_name:
        return new_path

    known_labels = {
        format_category_folder(category_id, category_name, candidate)
        for candidate in CATEGORY_FOLDER_FORMAT_EXAMPLES
    }
    known_labels.update(extra_legacy_labels)
    known_labels.discard(label)
    existing_paths = [
        os.path.join(parent, candidate)
        for candidate in known_labels
        if os.path.isdir(os.path.join(parent, candidate))
    ]
    if len(existing_paths) == 1:
        os.rename(existing_paths[0], new_path)
        print(f"Renamed category folder: {existing_paths[0]} -> {new_path}")
    elif len(existing_paths) > 1:
        print(
            "Multiple existing category folders found; leaving them in place: "
            + ", ".join(existing_paths)
        )
    return new_path


def category_path(
    base_path,
    game_name,
    category_id,
    category_name,
    folder_format=DEFAULT_CATEGORY_FOLDER_FORMAT,
):
    parent = os.path.join(base_path, "mods", game_name)
    return migrate_category_path(
        parent, category_id, category_name, folder_format
    )


def read_mod_id(folder_name):
    marker_path = os.path.join(folder_name, MOD_ID_MARKER)
    try:
        with open(marker_path, "r", encoding="ascii") as marker:
            return int(marker.read().strip())
    except (OSError, ValueError):
        pass

    try:
        with open(
            os.path.join(folder_name, "metadata.json"),
            "r",
            encoding="utf-8",
        ) as metadata_file:
            return int(json.load(metadata_file)["_mod"]["_idRow"])
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        return None


def scan_existing_mods(path):
    existing_ids = {}
    if not os.path.isdir(path):
        return existing_ids
    for entry in os.scandir(path):
        if entry.is_dir():
            mod_id = read_mod_id(entry.path)
            if mod_id is not None:
                existing_ids[mod_id] = entry.path
    return existing_ids


def write_mod_id_marker(folder_name, mod_id):
    marker_path = os.path.join(folder_name, MOD_ID_MARKER)
    with open(marker_path, "w", encoding="ascii") as marker:
        marker.write(str(mod_id))
