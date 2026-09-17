"""GameBanana HTTP API access."""

import json
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import requests

from .config import CONTENT_MODELS, FILE_SECTIONS, MOD_INDEX_PROPERTIES
from .paths import category_id_from_record


session = requests.Session()


def content_model(section):
    try:
        return CONTENT_MODELS[section]
    except KeyError as error:
        raise ValueError(f"Unsupported GameBanana section: {section}") from error


class _BreadcrumbParser(HTMLParser):
    """Extract GameBanana's structured breadcrumb without extra dependencies."""

    def __init__(self):
        super().__init__()
        self.in_breadcrumb = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_breadcrumb = (
                dict(attrs).get("id") == "StructuredDataBreadcrumb"
            )

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_breadcrumb = False

    def handle_data(self, data):
        if self.in_breadcrumb:
            self.parts.append(data)


def get_category_hierarchy(category_id, section="mods"):
    """Return (ID, name) pairs from the root category to the selected category.

    Category API records do not expose parents. The category page's JSON-LD
    breadcrumb includes every ancestor, including intermediate subcategories.
    Refuse incomplete breadcrumbs rather than silently creating a flat folder.
    """
    content_model(section)
    response = session.get(
        f"https://gamebanana.com/{section}/cats/{category_id}", timeout=30
    )
    response.raise_for_status()
    parser = _BreadcrumbParser()
    parser.feed(response.text)
    try:
        breadcrumb = json.loads("".join(parser.parts))
        hierarchy = []
        for entry in sorted(
            breadcrumb["itemListElement"], key=lambda entry: entry["position"]
        ):
            item = entry["item"]
            path = urlparse(item["@id"]).path.rstrip("/").split("/")
            if len(path) == 4 and path[1:3] == [section, "cats"]:
                name = item["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Missing category name")
                hierarchy.append((int(path[-1]), name))
        if (
            not hierarchy
            or hierarchy[-1][0] != category_id
            or len({item[0] for item in hierarchy}) != len(hierarchy)
        ):
            raise ValueError("Incomplete category breadcrumb")
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(
            f"Could not resolve category hierarchy for {category_id}"
        ) from error
    return hierarchy


def detect_source_type(input_str):
    """Compatibility helper for callers that only handle Mod submissions."""
    source_type, source_id, url_sort, section = detect_source(input_str)
    if section != "mods":
        raise ValueError("Use detect_source to retain non-Mod content sections")
    return source_type, source_id, url_sort


def detect_source(input_str):
    """Return scope, ID, URL sort, and content section without losing identity."""
    if not input_str.isdigit():
        parsed = urlparse(input_str)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "gamebanana.com", "www.gamebanana.com",
        }:
            raise ValueError(f"Expected a GameBanana URL: {input_str}")
        path_parts = parsed.path.strip("/").split("/")
        if not path_parts[-1].isdigit():
            response = session.get(
                input_str, timeout=30, allow_redirects=True
            )
            response.raise_for_status()
            parsed = urlparse(response.url)
            if parsed.hostname not in {"gamebanana.com", "www.gamebanana.com"}:
                raise ValueError(f"Not a GameBanana URL: {parsed.geturl()}")
            path_parts = parsed.path.strip("/").split("/")
        url_sort = parse_qs(parsed.query).get("_sSort", [None])[0]
        if path_parts[-1].isdigit():
            source_id = int(path_parts[-1])
            if len(path_parts) == 2 and path_parts[0] in {"members", "games"}:
                scope = "submitter" if path_parts[0] == "members" else "game"
                return scope, source_id, url_sort, "mods"
            section = path_parts[0]
            if section in CONTENT_MODELS:
                if len(path_parts) == 2:
                    return "mod", source_id, url_sort, section
                if len(path_parts) == 3 and path_parts[1] in {"cats", "games"}:
                    scope = "category" if path_parts[1] == "cats" else "game"
                    return scope, source_id, url_sort, section
        raise ValueError(f"Unsupported GameBanana URL: {parsed.geturl()}")

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
                return source_type, id_value, None, "mods"
        except Exception:
            pass
    return "category", id_value, None, "mods"


def get_category_name(category_id, mod_record=None):
    """Return a category name from an index record or the API."""
    if mod_record:
        for key in ("_aCategory", "_aSubCategory", "_aRootCategory"):
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


def get_files(mod_id, section="mods"):
    model = content_model(section)
    if section not in FILE_SECTIONS:
        return []
    response = session.get(
        f"https://gamebanana.com/apiv11/{model}/{mod_id}",
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


def get_mod_record(mod_id, section="mods"):
    if section != "mods":
        return get_mod_metadata(mod_id, (), section=section)
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


def get_mod_index(params, section="mods"):
    model = content_model(section)
    response = session.get(
        f"https://gamebanana.com/apiv11/{model}/Index",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_mod_metadata(mod_id, properties, section="mods"):
    model = content_model(section)
    # Other models have different property sets (e.g. Script has _sRawCode
    # but no _aFiles). ProfilePage returns the fields supported by that model.
    suffix = "" if section == "mods" else "/ProfilePage"
    response = session.get(
        f"https://gamebanana.com/apiv11/{model}/{mod_id}{suffix}",
        params={"_csvProperties": ",".join(properties)} if not suffix else None,
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
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            # Some Posts responses contain plain-text PHP warnings followed
            # by otherwise valid JSON. Accept only that known prefix; login
            # pages, HTML errors, and truncated JSON must still fail.
            prefix, separator, payload = response.text.partition("{")
            warnings = [line for line in prefix.splitlines() if line.strip()]
            if not separator or not warnings or not all(
                line.startswith("Warning: ") for line in warnings
            ):
                raise
            data = json.loads(separator + payload)
        page_records = data.get("_aRecords", [])
        records.extend(page_records)
        metadata = data.get("_aMetadata", {})
        if metadata.get("_bIsComplete", True) or not page_records:
            return records
        page += 1


def get_posts_with_replies(mod_id, section="mods"):
    model = content_model(section)
    posts = request_all_records(
        f"https://gamebanana.com/apiv11/{model}/{mod_id}/Posts"
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
