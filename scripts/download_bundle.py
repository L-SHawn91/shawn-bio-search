#!/usr/bin/env python3
"""CLI wrapper for the shawn_bio_search.download pipeline.

Run `python3 scripts/download_bundle.py -h` for usage, or install the package
and use the `shawn-bio-download` console script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shawn_bio_search.download.runner import main_cli


if __name__ == "__main__":
    sys.exit(main_cli())
