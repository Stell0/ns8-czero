# Standalone C0 consumer fixture

This fixture tests released Core and managed-file upgrades. Copied NS8 actions and image definitions are for inspection only. Keep native installation and publication outside this fixture.

Use the Core tag, compatible patch range and frozen lock in this consumer. Make Core changes in a separate upstream checkout.
For infrastructure updates, use `scripts/sync-upstream.py` with the trusted manifest. Preserve customizations and clear `needs_review` only after testing the resolution.

In the generated checkout, run `uv sync --frozen`, then `uv run --frozen python -m unittest discover -s tests`.
