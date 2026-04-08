# M004: Version Bump & Release Tag Cleanup — Context

**Gathered:** 2026-04-06
**Status:** Complete

## Why This Milestone

Dev tags (e.g. `v2.6.1-dev`) published to GitHub pollute the releases/tags list. The original issue also included `__version__` being out of sync, but that was fixed before M004 started.

## What Was Done

- Deleted `v2.6.1-dev` tag from local and remote
- Verified `__version__` and `pyproject.toml` already correct at `"2.6.1-dev"`
- Verified `_parse_version()` already strips pre-release suffixes
- Verified update checker already skips pre-release GitHub releases
