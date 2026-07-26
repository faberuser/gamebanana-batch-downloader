"""Backward-compatible imports for the former monolithic core module.

New code should import from the focused modules directly.
"""

from .api import (
    detect_source_type,
    get_category_name,
    get_files,
    get_mod_record,
    get_posts_with_replies,
    request_all_records,
    session,
)
from .config import (
    CATEGORY_FOLDER_FORMAT_EXAMPLES,
    DEFAULT_CATEGORY_FOLDER_FORMAT,
    DEFAULT_OUTPUT_ROOT as script_path,
    MOD_INDEX_PROPERTIES,
    SORT_ALIASES,
)
from .downloads import download_file, download_mod, parse_last_modified
from .metadata import write_mod_metadata
from .paths import (
    apply_timestamp,
    category_from_mod,
    category_id_from_record,
    category_path,
    format_category_folder,
    migrate_category_path,
    read_mod_id,
    sanitize_filename,
    scan_existing_mods,
)
from .service import parse_mods, parse_single_mod
from .state import failed


__all__ = [
    "CATEGORY_FOLDER_FORMAT_EXAMPLES",
    "DEFAULT_CATEGORY_FOLDER_FORMAT",
    "MOD_INDEX_PROPERTIES",
    "SORT_ALIASES",
    "apply_timestamp",
    "category_from_mod",
    "category_id_from_record",
    "category_path",
    "detect_source_type",
    "download_file",
    "download_mod",
    "failed",
    "format_category_folder",
    "get_category_name",
    "get_files",
    "get_mod_record",
    "get_posts_with_replies",
    "migrate_category_path",
    "parse_last_modified",
    "parse_mods",
    "parse_single_mod",
    "read_mod_id",
    "request_all_records",
    "sanitize_filename",
    "scan_existing_mods",
    "script_path",
    "session",
    "write_mod_metadata",
]
