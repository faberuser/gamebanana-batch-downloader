"""Compatibility entry point for users of the original single-file script."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from gamebanana_downloader.cli import main


if __name__ == "__main__":
    main()
