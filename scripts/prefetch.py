"""Pre-download a Foundry Local model by alias.

Usage: python scripts/prefetch.py <alias> [<alias> ...]

Requires foundry-local-sdk >= 1.1.0.
"""

from __future__ import annotations

import sys


def main(aliases: list[str]) -> int:
    if not aliases:
        print("usage: python scripts/prefetch.py <alias> [<alias> ...]", file=sys.stderr)
        return 2

    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager
    except ImportError:
        print(
            "ERROR: foundry-local-sdk >= 1.1.0 is not installed.\n"
            "       Run: pip install 'foundry-local-sdk>=1.1.0'",
            file=sys.stderr,
        )
        return 1

    FoundryLocalManager.initialize(Configuration(app_name="fl-nemotron-prefetch"))
    mgr = FoundryLocalManager.instance

    rc = 0
    for alias in aliases:
        model = mgr.catalog.get_model(alias)
        if model is None:
            print(f"  [SKIP] '{alias}' is not in the local catalog.", file=sys.stderr)
            rc = 1
            continue
        if model.is_cached:
            print(f"  [OK]   '{alias}' already cached.")
            continue
        print(f"  [..]   Downloading '{alias}' (id={model.id}) ...")
        model.download()
        print(f"  [OK]   '{alias}' downloaded.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
