# Personal Data candidate validation

This is producer development on original C0 main
`6845d45252a73327b7eabce38fe28fdc81e3e5d0`. Core0.50/schema0041 is a candidate;
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

Before schema0041, a focused run passed111 cases across Core lifecycle, real signed REST /
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
independent installs and schema0041 migration. Documentation validation covers maintained local
links; the private-denylist check covers the complete public contribution.

Extended original-main and candidate regression runs used separate disposable
containers and databases. The exact original base passed3373 cases without
database skips. An earlier candidate passed3406 cases and failed6 predecessor
assertions: three migration snapshots, one ordinary-space uniqueness constraint
snapshot and two frozen response contracts. These were repaired to assert the
new default-false personal column, replacement ordinary-space unique index and
strictly optional metadata; focused reruns passed all six. The frozen first candidate subsequently passed3435 actual Python/PostgreSQL/
packaging cases without database skips. That proof belongs to975bbd6, not the
uncommitted successor.

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
registered provider. WebTop domain administration and dedicated key creation work.
Initial per-user reads with the finite key returned401, including after attempts
to clear its expiry. A newly created dedicated key without expiry then verified
the selected main identity, six standard folders and the message inventory with200.
The finite predecessor and temporary diagnostic keys were revoked. Do not infer
that a product modification is needed, or that the expiry check alone explains
the earlier failures. The retained dedicated credential requires explicit revocation.

One local-only synthetic multipart message was delivered to the newly installed
Mail test mailbox. Exact-message reads, the shared C0 HTML extraction and the
attachment descriptions work. The message stayed unread before and after reads
using `set_seen=false`. The supported plain-text attachment download returned500,
including with persistent cookies and the documented machinery header. This is
an observed source API limitation, not a successful attachment import. C0 records
that failure and retries it; no alternative MIME index is guessed. No real user
message body was imported into production C0.

The new native discovery helper ran read-only in the installed C0 environment
and selected both test services as compatible through the canonical provider;
WebTop's relationship was checked through Mail. No C0 configuration or imported
content was changed. The new WebTop hostname still needs end-to-end DNS/TLS
verification; loopback HTTP probes do not establish that gate.

## Remaining gates

Resolve the installed WebTop attachment download failure without modifying the
product, exercise actual NethCTI transcript/summary records (the full interval
from1900 through the inclusive current window is empty), finish daily inventory /
backfill capacity and new-arrival throughput, and complete integration
credential provisioning/revocation. Local credential clearing reports pending
upstream revocation rather than claiming it happened.

Full Debian/Rocky native configuration, backup/restore, scheduler, privacy and
packaged-connector acceptance remain required. Then independently publish Core,
adopt its immutable release/lock and verify the released consumer. The switch
must remain disabled on existing installations until those gates pass.

## Preserved first candidate and successor

Commit `975bbd6a74a12b1090bce41f8782b0868f2bcddb` remains frozen in
[PR140](https://github.com/Stell0/ns8-czero/pull/140), with
[full acceptance43770452775](https://github.com/Stell0/ns8-czero/actions/runs/43770452775).
Its complete local job, Debian update and Rocky installation jobs passed.
The workflow concludes successfully; the optional Rocky screenshot upload failed
and is not counted as native test failure. Independent downloaded report/privacy/image audits passed against the frozen
source: eight privacy workflows,32 accessibility contexts, five scan/SBOM pairs,
three installed image identities and zero OAuth-query candidates.
Draft feedback checks passed; the PR merge gate correctly rejects a draft with
`ready_for_review_required`. No merge, independent Core release or deployment is
claimed from that result.

The successor adds recent-item collection during historical backfill, full status
for unvisited directory users, recipient-local transcript/summary links and
clearing local credentials after source/provider disconnection. Historical windows
remain pinned and do not falsely update current inventory completion. The current
source needs its own full/native proof; first-candidate evidence is not transferred.
The native backup case now seeds mappings, checkpoints, an exclusion, imported and
authored content plus a nonempty private credential file; it checks the restored
fence, retained authored content and imported payload cleanup. Standalone package
checks validate the Core fixture protocol; only the subsequent real native backup
run establishes the actual round trip.

The successor also fences startup through runagent before extraction workers run,
continues disconnected-source cleanup without live credentials, preserves immutable
call lookup identities independently of edited metadata, and identifies the owner's
personal space explicitly in discovery. Forward schema0041 preserves observed
username aliases and suspends ambiguous reuse; a private post-read directory check
rejects rename, disable and replacement races. The original0040 migration remains
unchanged. These changes require new exact-source package and native evidence.

The schema0041 successor focused check passes72 cases (including the populated0040
forward migration, rename/reuse quarantine, post-read immutable-ID/disable checks,
Core lifecycle and source fixtures). Separate HTTP/native-policy/backup/audit/fork
checks pass240 cases. Standalone wheel/archive migration, OCR and backup-fixture
checks pass6 cases on Python3.13 with external Python3.12 installs. These counts
are separate from the frozen975bbd6 full run. The current real HTTPS browser run
passes both personal-space cases; Node24 website checks pass33 unit cases plus
lint, formatting, types and build. Fresh full/native acceptance remains required.
The installed attachment API also returned500 on four spaced retries with the
machinery header; unread flags remained unchanged throughout.

The folder-inventory successor passes39 Core lifecycle/runner cases, including
stable resume after reordered folders and a fresh scan after folder-set changes.
It does not alter the Core package tree. Full acceptance43786727000 remains
frozen on393dedc; the folder-inventory successor requires its own full run.

The next successor passes76 Core/runner/adapter/native-identity cases and68 native
configuration/credential/backup cases (overlapping suites, not an aggregate).
Six independently installed wheel/archive/OCR cases pass on its changed Core
package. New cases cover exact summary-kind removal, late provenance updates with
unchanged body bytes, preserved local edits, credential rotation/clearing during
reads, and disconnection intent preceding a failed generation fence.

A private diagnostic also runs the actual C0 WebTop adapter against the installed
API through an SSH bridge: main identity, three eligible folders, safe synthetic
message extraction and explicit failed/unsupported attachment observations pass.
It performs GET reads only, publishes nothing in C0 and does not verify public
DNS/TLS. No NethCTI JWT is transferred by the additional diagnostics; its installed
proof remains the on-node profile and empty personal-history read.
