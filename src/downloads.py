"""Streaming files and downloading all assets for one mod."""

import os
import time
from email.utils import parsedate_to_datetime

from . import api, metadata, state
from .paths import (
    apply_timestamp,
    sanitize_filename,
)


def parse_last_modified(header_value):
    if not header_value:
        return None
    try:
        return parsedate_to_datetime(header_value).timestamp()
    except Exception:
        return None


def download_file(url, path, preserve_time=True, fallback_ts=None):
    if os.path.exists(path):
        if os.path.getsize(path) == 0:
            print(f"File {path} has 0kb. Redownloading.")
        else:
            print(f"File {path} already exists.")
            if preserve_time and fallback_ts is not None:
                apply_timestamp(path, fallback_ts)
            return "exists"

    for attempt in range(3):
        try:
            print(f"Downloading {os.path.basename(path)}")
            temporary_path = path + ".part"
            bytes_written = 0
            with api.session.get(
                url, stream=True, timeout=(15, 60)
            ) as response:
                response.raise_for_status()
                expected = response.headers.get("Content-Length")
                expected = (
                    int(expected)
                    if expected and expected.isdigit()
                    else None
                )
                last_reported_percentage = -1
                with open(temporary_path, "wb") as output:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if not chunk:
                            continue
                        output.write(chunk)
                        bytes_written += len(chunk)
                        if expected:
                            percentage = int(bytes_written / expected * 100)
                            if percentage >= last_reported_percentage + 5:
                                print(
                                    f"  {percentage}% "
                                    f"({bytes_written}/{expected} bytes)"
                                )
                                last_reported_percentage = percentage
                        elif bytes_written % (10 * 1024 * 1024) < len(chunk):
                            print(f"  downloaded {bytes_written} bytes")

                if expected is not None and bytes_written != expected:
                    raise OSError(
                        f"Incomplete download for {path}: expected "
                        f"{expected} bytes, got {bytes_written} bytes"
                    )
                os.replace(temporary_path, path)
                print(f"  done ({bytes_written} bytes)")

            if preserve_time:
                header_timestamp = parse_last_modified(
                    response.headers.get("Last-Modified")
                )
                apply_timestamp(
                    path,
                    header_timestamp
                    if header_timestamp is not None
                    else fallback_ts,
                )
            return "success"
        except KeyboardInterrupt:
            raise
        except Exception as error:
            temporary_path = path + ".part"
            if os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except Exception:
                    pass
            print(
                f"Failed to download {path} ({error}). Retrying in 5 "
                f"seconds for the {attempt + 1}/3 time."
            )
            time.sleep(5)

    print(f"Failed to download {path}. Skipping.")
    return "failed"


def _select_folder(path, mod_name, used_folders, existing_folder):
    folder_name = existing_folder or os.path.join(
        path, sanitize_filename(mod_name)
    )
    if existing_folder:
        if used_folders is not None:
            used_folders.add(folder_name)
        return folder_name

    if used_folders is not None:
        base_folder = folder_name
        suffix = 1
        while folder_name in used_folders:
            folder_name = f"{base_folder} ({suffix})"
            suffix += 1
        used_folders.add(folder_name)
    elif os.path.exists(folder_name):
        suffix = 1
        while os.path.exists(f"{folder_name} ({suffix})"):
            suffix += 1
        folder_name = f"{folder_name} ({suffix})"
    return folder_name


def download_mod(
    mod,
    path,
    source_id,
    preserve_time=True,
    used_folders=None,
    existing_folder=None,
):
    mod_name = mod["_sName"]
    folder_name = _select_folder(
        path, mod_name, used_folders, existing_folder
    )
    os.makedirs(folder_name, exist_ok=True)

    fallback_timestamp = (
        mod.get("_tsDateModified") or mod.get("_tsDateAdded")
    )
    image_failures = []
    for image in mod["_aPreviewMedia"]["_aImages"]:
        image_url = image["_sBaseUrl"] + "/" + image["_sFile"]
        status = download_file(
            image_url,
            os.path.join(folder_name, image["_sFile"]),
            preserve_time=preserve_time,
            fallback_ts=fallback_timestamp,
        )
        if status == "failed":
            image_failures.append(image_url)

    file_failures = []
    for file_record in api.get_files(mod["_idRow"]):
        status = download_file(
            file_record["url"],
            os.path.join(folder_name, file_record["name"]),
            preserve_time=preserve_time,
            fallback_ts=file_record.get("ts") or fallback_timestamp,
        )
        if status == "failed":
            file_failures.append(file_record["name"])

    metadata_failed = False
    if not image_failures and not file_failures:
        try:
            print("Writing metadata.json")
            metadata.write_mod_metadata(
                mod["_idRow"],
                folder_name,
                source_id,
                mod_index_record=mod,
                preserve_time=preserve_time,
            )
        except Exception as error:
            print(f"Failed to write metadata for {mod_name}: {error}")
            metadata_failed = True

    if metadata_failed or image_failures or file_failures:
        state.failed.append(
            (
                mod_name,
                f"https://gamebanana.com/mods/{mod['_idRow']}",
                image_failures,
                file_failures,
            )
        )
        return None

    return folder_name
