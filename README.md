# GameBanana Downloader

A command-line archiver for GameBanana submissions. It can download an individual
submission or batch download a category, game section, or mod submitter,
including available files, preview images, and metadata.

## Features

- Individual, category, game, and submitter batch downloads
- Mods, Sounds, Tutorials, Tools, Scripts, Projects, and Concepts URLs
- GameBanana sorting such as newest, oldest, most liked, and most downloaded
- Resume support that skips completed mods before requesting their details
- Metadata, comments, and replies for every mod
- Original server timestamps when available
- Safe handling of duplicate mod names
- Configurable category folders' name
- Category folders preserve the full GameBanana parent/subcategory hierarchy

## Requirements

- Python 3.12 or newer

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

Download a mod:

```bash
gamebanana https://gamebanana.com/mods/497545
```

Download a category:

```bash
gamebanana https://gamebanana.com/mods/cats/7559
```

Download all game's mods:

```bash
gamebanana https://gamebanana.com/games/6498
```

Download all submmiter's submissions:

```bash
gamebanana https://gamebanana.com/members/1661569
```

Prioritize the most downloaded mods:

```bash
gamebanana --sort most-downloaded https://gamebanana.com/mods/cats/7559
```

The `_sSort` value in a GameBanana URL is also honored:

```bash
gamebanana "https://gamebanana.com/mods/cats/7559?_sSort=Generic_Oldest"
```

Resume a large category without making detail and file requests for completed
mods:

```bash
gamebanana --skip-existing --sort oldest https://gamebanana.com/mods/cats/7559
```

Save under a custom location and slow the batch rate:

```bash
gamebanana --path "C:\Downloads" --delay 5 https://gamebanana.com/mods/cats/7559
```

Run `gamebanana --help` for every option and supported sort.

### Download only directly assigned category submissions

Use `--direct-category-only` to exclude submissions assigned to any subcategory:

```bash
python gamebanana.py --direct-category-only https://gamebanana.com/mods/cats/9139
python gamebanana.py --direct-category-only --skip-existing https://gamebanana.com/mods/cats/3325
```

This also works when the selected category is nested inside another category,
and with supported non-Mod category URLs. Without the flag, category downloads
continue to include subcategories. Game, submitter, and individual submission
URLs cannot use this flag.

The downloader scans all index pages and compares assigned category IDs before
downloading files or metadata. Large categories may take time to scan even when
few submissions match. Sorting, folder formats, and resume behavior still apply;
existing downloads are not moved or deleted. All index pages are scanned before downloads begin so the preview and download
progress count only direct matches (for example, `1/54`, `2/54`). Scanning has
separate page progress. With `--skip-existing`, completed matches still count
toward this total and are reported as skipped.

### Whole-game archives

A whole-game URL downloads all supported sections by default (`mods`, `sounds`,
`tuts`, `tools`, `scripts`, `projects`, `concepts`, and `wips`). Empty sections
are skipped. Select or exclude sections for each invocation:

```bash
python gamebanana.py https://gamebanana.com/games/4660
python gamebanana.py --sections sounds,tuts https://gamebanana.com/games/30
python gamebanana.py --exclude-sections wips,projects https://gamebanana.com/games/30
```

Both whole-game and section-specific game downloads place each submission in
its assigned category, preserving every ancestor. Direct parent-category mods
stay in that parent, alongside its subcategory folders. No
`--direct-category-only` flag is needed for a whole game.

```text
mods/
└── Counter-Strike- Global Offensive/
    └── Maps/
        └── [Combat-Skill]/
        │   └── [Arsenal]/
        │       └── Submission Name/
        └── gm_construct/
```

Root categories stay plain; subcategories use `[Name]` by default, including
category and individual-submission CLI downloads. Only category labels get
brackets, not submission names. Use `--no-category-brackets` for plain names;
`--category-folder-format` still controls the label inside the brackets.
Use `--flat` to disable category organization for game downloads.

With `--path`, organized games use `PATH/SECTION/Game/Category/...`.
Existing flat archives and unbracketed subcategory directories are not moved
into the new layout automatically. Use `--flat` to resume a flat game archive,
`--no-category-brackets` to reuse plain category folders, or move completed
submission folders into their new locations before using `--skip-existing`.
Section selection applies to every whole-game URL in the invocation; use
separate commands for games requiring different selections.

### Other content sections

The URL determines the content section. For example:

```bash
gamebanana https://gamebanana.com/sounds/92865
gamebanana https://gamebanana.com/sounds/cats/3060
gamebanana https://gamebanana.com/sounds/games/5892
gamebanana https://gamebanana.com/tuts/games/5892
```

The same individual, category, and game-section URL forms work for `mods`,
`sounds`, `tuts`, `tools`, `scripts`, `projects`, `concepts`, and `wips`. Unsupported URL
sections are rejected rather than interpreted as mod IDs. Game IDs and `/games/ID` select all supported sections; `/members/ID`
continues to select Mods. Explicit URLs such as `/sounds/games/ID` select only
that section. Use full URLs to avoid ambiguous numeric IDs.

Each section has its own output directory, such as
`sounds/Sonic Adventure DX/Other-Misc/Submission Name`. Game-section batches
use category hierarchies under `sounds/Sonic Adventure DX`. With `--path`,
organized games use the same layout below that path; flat non-Mod batches use
section subdirectories such as `C:\Downloads\sounds\game_5892`. Individual
submissions with `--path` use names such as `sound_92865`.

Sounds, Tools, and WiPs download their attached files when present. Tutorials, Scripts, Projects,
and Concepts archive their text, code (when present), comments, and preview
images in the submission folder; text and code are stored in `metadata.json`.
Resume metadata records the section so overlapping IDs cannot cause a sound
to be mistaken for a completed mod.

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
renamed automatically for plain category paths. Bracketed subcategory paths
are created without renaming existing folders. If multiple matching folders already exist, they are
left untouched to avoid merging data unexpectedly.

The format applies to every level of the category hierarchy. For example,
category 6090 is saved under `Super Smash Bros. Ultimate/Stages/[Other-Misc]`,
while category 3319 uses `Super Smash Bros. Ultimate/Other-Misc`. Deeper
subcategories preserve all intermediate folders. With `--path`, Mods category
hierarchies are placed directly inside the chosen directory; other content
sections get their own subdirectory as described above.

Existing flat subcategory folders are left in place, since their contents may
mix unrelated categories. Move previously downloaded mods into their correct
category folders to reuse them with `--skip-existing`. If the category page's
hierarchy cannot be read, the download stops instead of using a flat path.

## Output

By default, downloads are written below the current directory:

```text
mods/
└── Super Smash Bros. Ultimate/
    └── Skins/
        └── Ness/
            └── Mod Name/
                ├── metadata.json
                ├── preview.png
                └── mod-file.zip
```

`metadata.json` is written only after a mod finishes successfully. With
`--skip-existing`, its embedded mod ID lets later runs skip completed mods
without making per-mod API calls.

## Development

Run the standard-library test suite:

```bash
python -m unittest discover -s tests -v
```

Tests use mocked API responses and do not download mods.

## Build an executable

Install the build dependency and run PyInstaller from the repository root:

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller --clean --noconfirm gamebanana.spec
```
