#!/usr/bin/env python3
"""Backward-compatible entry point for the paperkit package."""
import sys

from paperkit import core

# Imports of ``fetch_papers`` receive the implementation module so existing
# callers that patch module globals keep working during the migration.
if __name__ != "__main__":
    sys.modules[__name__] = core
else:
    raise SystemExit(core.main())
