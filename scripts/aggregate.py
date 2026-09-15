#!/usr/bin/env python3
"""Compatibility entry point for Rein's aggregation implementation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rein.judge.aggregate import main, summarize  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
