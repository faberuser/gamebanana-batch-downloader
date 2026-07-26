"""Portable entry point and source-tree package shim."""

import os

# When this file is imported from the repository root, expose ``src`` as the
# package path instead of shadowing the installed ``gamebanana`` package.
__path__ = [os.path.join(os.path.dirname(__file__), "src")]

from gamebanana.cli import main


if __name__ == "__main__":
    main()
