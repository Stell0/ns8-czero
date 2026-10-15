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

Packaging checks install the built wheel into a clean environment outside the
checkout and exercise its imports, metadata and migrations. PostgreSQL/pgvector
checks require an isolated `CZERO_TEST_DATABASE_URL`; never point tests at live data.
Only Core is installed: the NS8 SDK and reference FastAPI application are separate.

Application code can import `czero_core.core_health` and construct the domain
services against `czero_core.Database`. Database-backed operations require the
packaged schema: set `CZERO_DATABASE_URL` privately and run
`python -m czero_core.migrate` before serving requests. Repeated migration preserves
the knowledge-space identity. Never place a database URL or identity/provider
secret in source code or application logs.

Version `0.24.1` is the initial distribution packaging patch, with the existing
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

The workflow is prepared and locally validated; consult PLAN.md for actual
executed publication and consumer tests before selecting an artifact.
