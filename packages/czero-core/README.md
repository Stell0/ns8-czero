# C0 Core

Reusable Python services for C0 applications, independent of the NethServer
agent SDK and the FastAPI transport. This package owns the PostgreSQL schema,
shared application operations and trusted deterministic worker.

One database represents one shared knowledge space. Services implement persisted
Reader/Editor/Admin membership, browser/OIDC sessions, objects and typed relations,
immutable document evidence/citations, authored Wiki/claims/graph, text and optional
semantic retrieval, deterministic jobs and bounded external-client grants.
The application supplies trusted adapters, authenticated actors and HTTP/MCP
transport. Requests never select Python imports, arbitrary SQL or shell commands.

See the repository [README](https://github.com/Stell0/ns8-czero/blob/main/README.md)
for supported interfaces, limits and tested versions. Native module lifecycle,
container management, route configuration and backups remain in numbered NS8
scripts outside this package. Optional providers do not determine authorization;
text search remains independent of inference. Generative operations stay outside
the runtime.

## Building and verifying

From the repository root:

```sh
uv build --no-sources packages/czero-core --out-dir /tmp/czero-core-dist
python -m pytest tests/packaging
```

Packaging checks install both wheel and source archive into separate clean
environments outside the checkout and exercise imports, metadata and migrations. PostgreSQL/pgvector
checks require an isolated `CZERO_TEST_DATABASE_URL`; never point tests at live data.
Only Core is installed: the NS8 SDK and reference FastAPI application are separate.

Application code can import `czero_core.core_health` and construct the domain
services against `czero_core.Database`. Database-backed operations require the
packaged schema: set `CZERO_DATABASE_URL` privately and run
`python -m czero_core.migrate` before serving requests. Repeated migration preserves
the knowledge-space identity. Never place a database URL or identity/provider
secret in source code or application logs.

Version `0.24.2` corrects distribution instructions after the initial verified
`0.24.1` release, with the existing
`0013_oauth_consent` schema and unchanged runtime contracts. The compatible consumer range is `>=0.24.1,<0.25.0`. Publication and automatic
fork-update evidence is recorded in the repository PLAN.md.

Licensed GPL-3.0-or-later; the complete license is included in both distributions.

## Core artifact publication

`.github/workflows/publish-core.yml` handles `core-v<package-version>` tags,
independently of NS8 module releases. It checks the exact checkout/source,
successful local CI and both native distributions before building artifacts.
The exact wheel/source archive is tested, including packaged PostgreSQL
migrations, before a separate narrowly scoped job creates a draft release,
checks its uploaded hashes and publishes it without replacing the module's
latest release. Replays must match existing artifact bytes; published files
are never clobbered.

Core 0.24.1 is published with verified checksums at
https://github.com/Stell0/ns8-czero/releases/tag/core-v0.24.1.
Consult PLAN.md for subsequent exact-source publication gates and actual
consumer/Renovate evidence; a started workflow does not establish acceptance.

Release builds also normalize generated source-archive ownership, timestamps,
permissions and gzip metadata with `scripts/normalize-core-sdist.py` and the
source commit's `SOURCE_DATE_EPOCH`. Wheel and normalized archive rebuild hashes
are checked; package contents are preserved. Setuptools source archives alone
retain build-host metadata, so raw uv sdist output is not a replayable release
artifact. This development helper stays outside the installed Core package.
Build the final wheel from the normalized archive under umask 022 to avoid
checkout group-write modes changing ZIP metadata. Its bytes reproduce the
published wheel across build hosts.

## Independent installation

Use a Python 3.12–3.14 virtual environment and the verified release assets, or
the immutable Git tag/subdirectory source:

```sh
uv pip install "czero-core @ git+https://github.com/Stell0/ns8-czero.git@core-v0.24.1#subdirectory=packages/czero-core"
```

For applications, declare the compatible range `>=0.24.1,<0.25.0` and the
reviewed Git tag in `[tool.uv.sources]`, then commit uv.lock. Never replace the
released source with a local checkout implicitly. The template producer can
opt in with `CZERO_CORE_SOURCE=local`; this affects only its build environment.
Minor/breaking releases require separate compatibility and migration review.
