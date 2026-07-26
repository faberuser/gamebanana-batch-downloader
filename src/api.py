"""GameBanana HTTP API access."""

from urllib.parse import parse_qs, urlparse

import requests

from .config import MOD_INDEX_PROPERTIES
from .paths import category_id_from_record


session = requests.Session()


def detect_source_type(input_str):
    """Detect the input type and ID, plus any sort found in its URL."""
    if not input_str.isdigit():
        parsed = urlparse(input_str)
        path_parts = parsed.path.rstrip("/").split("/")
        if not path_parts[-1].isdigit():
            response = session.get(
                input_str, timeout=30, allow_redirects=True
            )
            response.raise_for_status()
            parsed = urlparse(response.url)
            path_parts = parsed.path.rstrip("/").split("/")
        url_sort = parse_qs(parsed.query).get("_sSort", [None])[0]

        if "members" in path_parts:
            return "submitter", int(path_parts[-1]), url_sort
        if "games" in path_parts:
            return "game", int(path_parts[-1]), url_sort
        if "mods" in path_parts and "cats" not in path_parts:
            return "mod", int(path_parts[-1]), url_sort
        try:
            return "category", int(path_parts[-1]), url_sort
        except ValueError as error:
            raise ValueError(
                f"Could not extract ID from URL: {parsed.geturl()}"
            ) from error

    id_value = int(input_str)
    for model, source_type in (
        ("Game", "game"),
        ("Member", "submitter"),
    ):
        try:
            response = session.get(
                f"https://gamebanana.com/apiv11/{model}/{id_value}",
                params={"_csvProperties": "_idRow"},
                timeout=15,
            )
            if (
                response.status_code == 200
                and response.json().get("_idRow") == id_value
            ):
                return source_type, id_value, None
        except Exception:
            pass
    return "category", id_value, None


def get_category_name(category_id, mod_record=None):
    """Return a category name from an index record or the API."""
    if mod_record:
        for key in ("_aSubCategory", "_aRootCategory"):
            category = mod_record.get(key)
            if category_id_from_record(category) == category_id:
                return category.get("_sName")

    for model in ("ModCategory", "Category"):
        try:
            response = session.get(
                f"https://gamebanana.com/apiv11/{model}/{category_id}",
                params={"_csvProperties": "_sName"},
                timeout=15,
            )
            if response.status_code == 200:
                name = response.json().get("_sName")
                if name:
                    return name
        except Exception:
            pass
    return None


def get_files(mod_id):
    response = session.get(
        f"https://gamebanana.com/apiv11/Mod/{mod_id}",
        params={"_csvProperties": "_aFiles"},
        timeout=30,
    )
    response.raise_for_status()
    return [
        {
            "name": file_record["_sFile"],
            "url": file_record["_sDownloadUrl"],
            "ts": file_record.get("_tsDateAdded"),
        }
        for file_record in response.json()["_aFiles"]
    ]


def get_mod_record(mod_id):
    response = session.get(
        f"https://gamebanana.com/apiv11/Mod/{mod_id}",
        params={"_csvProperties": ",".join(MOD_INDEX_PROPERTIES)},
        timeout=30,
    )
    response.raise_for_status()
    mod = response.json()
    if mod.get("_sErrorCode"):
        raise RuntimeError(mod)
    return mod


def get_mod_index(params):
    response = session.get(
        "https://gamebanana.com/apiv11/Mod/Index",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_mod_metadata(mod_id, properties):
    response = session.get(
        f"https://gamebanana.com/apiv11/Mod/{mod_id}",
        params={"_csvProperties": ",".join(properties)},
        timeout=30,
    )
    response.raise_for_status()
    mod = response.json()
    if mod.get("_sErrorCode"):
        raise RuntimeError(mod)
    return mod


def request_all_records(url):
    page = 1
    records = []
    while True:
        response = session.get(
            url,
            params={"_nPage": page, "_nPerpage": 50},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        page_records = data.get("_aRecords", [])
        records.extend(page_records)
        metadata = data.get("_aMetadata", {})
        if metadata.get("_bIsComplete", True) or not page_records:
            return records
        page += 1


def get_posts_with_replies(mod_id):
    posts = request_all_records(
        f"https://gamebanana.com/apiv11/Mod/{mod_id}/Posts"
    )
    for post in posts:
        post_id = post.get("_idRow")
        if post_id and post.get("_nReplyCount", 0):
            post["_aReplies"] = request_all_records(
                f"https://gamebanana.com/apiv11/Post/{post_id}/Posts"
            )
        else:
            post["_aReplies"] = []
    return posts
