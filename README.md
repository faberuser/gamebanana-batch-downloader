# GameBanana Downloader

A command-line archiver for GameBanana mods. It can download one mod or batch
download a category, game, or submitter, including preview images and optional
metadata.

## Features

- Individual, category, game, and submitter batch downloads
- GameBanana sorting such as newest, oldest, most liked, and most downloaded
- Resume support that skips completed mods before requesting their details
- Optional metadata, comments, and replies
- Original server timestamps when available
- Safe handling of duplicate mod names
- Configurable category folders' name

## Requirements

- Python 3.9 or newer

## Installation

Clone or download this repository, then install it:

```bash
python -m pip install .
```

This provides the `gamebanana` command. For development, use:

```bash
python -m pip install -e .
```

The original portable invocation remains supported without installation:

```bash
python gamebanana.py --help
```

## Usage

Download one mod:

```bash
gamebanana https://gamebanana.com/mods/497545
```

Download a category with metadata:

```bash
gamebanana --metadata https://gamebanana.com/mods/cats/7559
```

Prioritize the most downloaded mods:

```bash
gamebanana --sort most-downloaded https://gamebanana.com/mods/cats/5299
```

The `_sSort` value in a GameBanana URL is also honored:

```bash
gamebanana "https://gamebanana.com/mods/cats/5299?_sSort=Generic_Oldest"
```

Resume a large category without making detail and file requests for completed
mods:

```bash
gamebanana --skip-existing --sort oldest https://gamebanana.com/mods/cats/5299
```

Save under a custom location and slow the batch rate:

```bash
gamebanana --path "C:\Downloads" --delay 5 https://gamebanana.com/mods/cats/5299
```

Run `gamebanana --help` for every option and supported sort.

### Category folder format

Use `--category-folder-format` with the `{id}` and `{name}` placeholders. Quote
the format so the shell passes it as one argument.

| Desired folder | Option                                        |
| -------------- | --------------------------------------------- |
| `Ness`         | `--category-folder-format "{name}"` (default) |
| `7559`         | `--category-folder-format "{id}"`             |
| `Ness (7559)`  | `--category-folder-format "{name} ({id})"`    |
| `7559 (Ness)`  | `--category-folder-format "{id} ({name})"`    |
| `7559 - Ness`  | `--category-folder-format "{id} - {name}"`    |

For example:

```bash
gamebanana --category-folder-format "{name} ({id})" https://gamebanana.com/mods/cats/7559
```

When changing formats, a single folder matching one of the layouts above is
renamed automatically. If multiple matching folders already exist, they are
left untouched to avoid merging data unexpectedly.

## Output

By default, downloads are written below the current directory:

```text
mods/
└── Super Smash Bros. Ultimate/
    └── Ness/
        └── Mod Name/
            ├── .gamebanana-mod-id
            ├── metadata.json
            ├── preview.png
            └── mod-file.zip
```

The ID marker is written only after a mod finishes successfully. With
`--skip-existing`, it lets later runs skip completed mods without making
per-mod API calls. Older folders are recognized by name and receive a marker
during the first resumed run.

## Development

Run the standard-library test suite:

```bash
python -m unittest discover -s tests -v
```

Tests use mocked API responses and do not download mods.
