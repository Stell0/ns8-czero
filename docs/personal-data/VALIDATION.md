# Personal Data candidate validation

This is producer development on original C0 main
`6845d45252a73327b7eabce38fe28fdc81e3e5d0`. Core0.50/schema0040 is a candidate;
the released consumer remains pinned to Core0.49. No production deployment,
source-product modification or source-product pull request is part of this work.

## Executed checks

Disposable PostgreSQL fixtures exercise pre-login provisioning, rename and
username reuse, account blocks, own-space authority, OAuth/API-key ceilings,
local overrides/exclusions, suspended sessions, interrupted inventories,
post-read binding checks, publication fencing, payload retirement and cleanup.
The actual signed REST and current MCP SDK tests exercise the selected space;
synthetic source fixtures exercise participants, transcript row IDs, transfers,
unstable inventories, UID reuse, MIME parameters and shared/public mail exclusions.

The final focused run passed103 cases across Core lifecycle, real signed REST /
MCP, source adapters, native configuration, credential files and backup contracts,
without database skips. Separate current contract checks passed61 cases. Four real
HTTPS/browser cases passed for personal-space operations, Reader-owned Write API
keys, Admin sharing restrictions and light/dark themes. Node24.22.2 frontend
lint/format/types/build and33 unit cases passed. Native JavaScript controllers
passed28 cases; Carbon settings lint/format/build passed with the frozen lock
and the available host Node25.8.1, not native CI's Node24 runtime.

A disposable rootless pod with the actual non-root image UID10001 read the
mode-0600 runtime/credential copies successfully; canonical host-file ownership
remained unchanged. This verifies file delivery, not installed scheduler behavior.
Per-run copies are removed before container teardown, including failure paths;
stale copies from killed invocations are collected on subsequent runs. Detailed
user coverage remains in private status storage rather than service stdout.

The final standalone Core wheel/archive/OCR suite passed6 cases, including
independent installs and schema0040 migration. Documentation validates702 local
links; the private-denylist check passes for all77 changed public files.

Extended original-main and candidate regression runs used separate disposable
containers and databases. The exact original base passed3373 cases without
database skips. An earlier candidate passed3406 cases and failed6 predecessor
assertions: three migration snapshots, one ordinary-space uniqueness constraint
snapshot and two frozen response contracts. These were repaired to assert the
new default-false personal column, replacement ordinary-space unique index and
strictly optional metadata; focused reruns passed all six. This is not a final
exact-source full-suite pass.

Initial diagnostics also exposed missing website assets, an absent sample
dependency and temporary storage quota. A final packaging attempt with a read-only
source mount failed because setuptools writes package metadata; the writable
isolated-worktree rerun is separate evidence. Failed evidence stays outside Git.
An interrupted or failed diagnostic run is not an acceptance pass.

## Installed capability probes

An operator-selected NethVoice test user had a usable non-persistent session.
The installed `/user/me` verified the expected username and a current extension;
personal transcription history returned a valid empty inventory. This verifies
session/profile/history access, not an actual transcript or summary read.
No unexpired persistent token was available for that selected user, so persistent
API access remains unverified. The inspected persistent-token audience set
contains no C0 audience. No audience
was impersonated and no super-admin token or personal password was copied.

A new WebTop1.5.18 / Mail1.9.3 test installation was configured against the same
registered provider. WebTop's domain administration API and dedicated domain-key
creation worked. Per-user mail reads returned401, including after registering
the selected directory profile and testing the supported no-expiry setting.
The original finite key expiry was restored. Directory existence, canonical
provider binding, service bind credential and key digest comparisons passed
without exposing their values; per-user reads still did not authenticate. The inspected expiry check is
suspicious, but does not by itself explain the observed authentication failure.
Do not advertise this installed mail connection as operational.

The new native discovery helper ran read-only in the installed C0 environment
and selected both test services as compatible through the canonical provider;
WebTop's relationship was checked through Mail. No C0 configuration or imported
content was changed. The new WebTop hostname still needs end-to-end DNS/TLS
verification; loopback HTTP probes do not establish that gate.

## Remaining gates

Resolve installed WebTop authentication without the excluded credential
exceptions, exercise actual NethCTI transcript/summary records, finish daily
inventory/backfill capacity and new-arrival coverage, and complete integration
credential provisioning/revocation. Local credential clearing reports pending
upstream revocation rather than claiming it happened.

Full Debian/Rocky native configuration, backup/restore, scheduler, privacy and
packaged-connector acceptance remain required. Then independently publish Core,
adopt its immutable release/lock and verify the released consumer. The switch
must remain disabled on existing installations until those gates pass.
