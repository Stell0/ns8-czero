# Standalone C0 consumer fixture

Read README.md and PLAN.md. This is original M13 acceptance material, not a
configured NS8 application. Do not install or run the copied native actions or
publish module images. Managed infrastructure is present for update review.

Core is a released Git-tag/subdirectory dependency with uv.lock and no local
Core source tree. Use native Renovate and preserve its compatible minor range.
Use scripts/sync-upstream.py with the explicit trusted manifest for infrastructure
updates. Preserve customized files and resolve their needs_review flags only
after relevant tests; do not reset the baseline to hide a conflict.

Run `uv sync --frozen` and `uv run --frozen python -m unittest discover -s tests`.
Keep .venv, logs, secrets and private live fixtures outside Git. Repository C0
skills delegate native development to installed NethServer skills, but this
fixture authorizes no native/live operations. Any contribution requiring the
actual Core source must use a separate upstream checkout.
