"""Shared configuration constants."""

import os


DEFAULT_OUTPUT_ROOT = os.getcwd()

SORT_ALIASES = {
    "newest": "Generic_Newest",
    "oldest": "Generic_Oldest",
    "latest-modified": "Generic_LatestModified",
    "new-updated": "Generic_NewAndUpdated",
    "latest-updated": "Generic_LatestUpdated",
    "a-z": "Generic_Alphabetically",
    "z-a": "Generic_ReverseAlphabetically",
    "most-liked": "Generic_MostLiked",
    "most-viewed": "Generic_MostViewed",
    "most-commented": "Generic_MostCommented",
    "latest-comment": "Generic_LatestComment",
    "most-downloaded": "Generic_MostDownloaded",
}

MOD_INDEX_PROPERTIES = [
    "_idRow",
    "_sName",
    "_sProfileUrl",
    "_tsDateAdded",
    "_tsDateModified",
    "_aPreviewMedia",
    "_aSubmitter",
    "_aGame",
    "_aRootCategory",
    "_aCategory",
]

DEFAULT_CATEGORY_FOLDER_FORMAT = "{name}"
CATEGORY_FOLDER_FORMAT_EXAMPLES = (
    "{name}",
    "{id}",
    "{name} ({id})",
    "{id} ({name})",
    "{id} - {name}",
)
