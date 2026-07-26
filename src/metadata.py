"""Metadata and comment archive writing."""

import json
import os

from . import api
from .paths import apply_timestamp


METADATA_PROPERTIES = [
    "_idRow",
    "_sName",
    "_sProfileUrl",
    "_sVersion",
    "_sText",
    "_tsDateAdded",
    "_tsDateModified",
    "_aSubmitter",
    "_aGame",
    "_aRootCategory",
    "_nViewCount",
    "_nLikeCount",
    "_nPostCount",
    "_bIsObsolete",
    "_aFiles",
    "_aPreviewMedia",
]


def write_mod_metadata(
    mod_id,
    folder_name,
    category_id,
    mod_index_record=None,
    preserve_time=True,
):
    mod = api.get_mod_metadata(mod_id, METADATA_PROPERTIES)
    metadata = {
        "_categoryId": category_id,
        "_mod": mod,
        "_modIndexRecord": mod_index_record,
        "_comments": api.get_posts_with_replies(mod_id),
    }
    metadata_path = os.path.join(folder_name, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, ensure_ascii=False, indent=2)
    if preserve_time:
        timestamp = mod.get("_tsDateModified") or mod.get("_tsDateAdded")
        apply_timestamp(metadata_path, timestamp)
