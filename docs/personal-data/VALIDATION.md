# Personal Data candidate validation

This candidate is based on original C0 main
`6845d45252a73327b7eabce38fe28fdc81e3e5d0`. Core0.50/schema0041 is independently
published; app0.68 stages its released tag/lock adoption, with consumer acceptance
still pending. No production deployment,
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
content was changed. The initial hostname lacked DNS. A free hostname already resolving to the test
node was subsequently configured with a valid certificate. The actual C0 adapter
now passes identity, eligible-folder, safe synthetic-message and unchanged unread
checks using normal verified public HTTPS. Attachment download still returns500;
no C0 publication is performed by these source probes.

## Remaining gates

Exercise actual NethCTI transcript/summary records (the full interval
from1900 through the inclusive current window is empty), finish daily inventory /
backfill capacity and new-arrival throughput, and complete integration
credential provisioning/revocation. Local credential clearing reports pending
upstream revocation rather than claiming it happened.

Exact released-consumer Debian/Rocky configuration, backup/restore, scheduler,
privacy and packaged-connector acceptance remain required. Independent Core
publication and immutable consumer adoption are recorded below. The switch
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

Native Debian393dedc fails at the first status read: api-cli and the NS8 settings
client omit task data (`null`), while both new read actions originally required an
object. The runner service itself starts successfully. Subsequent backup failures
in that run follow the aborted setup and are retained as failures, not acceptance.
The successor accepts null or an empty object for both read actions and rejects
unexpected fields/types;70 native configuration/backup unit cases pass. A new full
native run must exercise the actual nonempty backup round trip after this fix.


The final message-inventory check passes42 Core/runner cases. An unsupported or
failed attachment does not prevent independently confirmed removal of another
message after stable inventories; attachment failures remain visible as partial
coverage. Source deletion still requires the exact authenticated read policy.
The native credential command explicitly uses `--data -` to read private JSON
from stdin rather than command arguments.

The runner disables Podman's container logger for its private pipe. A real local
Podman round trip verifies the actual `none` log driver and delivery of a
synthetic binding request/reply without the marker appearing in container logs.
This is additional private-protocol evidence, not a substitute for native root
journald positive-control audits.71 native configuration/backup checks pass.

The scoped-mismatch successor passes44 Core/runner cases and71 native configuration/
backup checks. A two-source fixture verifies that a known mismatch retires only
the incompatible instance, preserves the healthy connection's published body and
keeps personal ownership active. An unscoped mismatch retains both copies. The
actual CLI executes this cleanup without opening the unavailable credential file;
the native helper also skips directory/credential reads when bindings are unverified.

NethCTI's configured public HTTPS API endpoint now passes an on-node probe with
redirects refused: the selected user's profile and empty personal-history response
match the connector contract. The session token stays on the node; no token is
returned, printed or saved by that probe. Actual transcript/summary content remains
unverified until a test record exists.


## Independent Core publication and consumer adoption

[Core0.50.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.50.0) is
immutably published from `280ca06639bf6df55082aca397c2a6a585d988e0` by
[publisher43800162081](https://github.com/Stell0/ns8-czero/actions/runs/43800162081).
Exact full [43792034668](https://github.com/Stell0/ns8-czero/actions/runs/43792034668)
and source promotion pass. The independent archived-source artifact audit accepts
both native distributions, their personal mappings/checkpoints/exclusions,
restored credential file, retained authored knowledge, publication fence and
physical import cleanup, plus the required browser/privacy/image/scan evidence.
The earlier393dedc native input-contract failure remains preserved.

Downloaded wheel SHA256:
`a53c7b7cc2b3f45f4f7b6cda89da3e78b7b64f8c70cbed5ba7b557079762ad4b`.
Downloaded archive SHA256:
`836e19e5ec08edfb1f083f733ca16ee98e4e7761c6260782933bfe4ee1cdd2c8`.
Checksums, runtime metadata, license and packaged0041 migration inspection pass.
The Core package tree is `b84309dd17fbbe5f86bcf789602e82cead8fde38`; later app
fixes and consumer adoption must not change it or replace the tag/assets.

The app0.68 consumer manifest and frozen lock select `core-v0.50.0` at that exact
commit with `>=0.50.0,<0.51.0`; patch-only updater bounds match. A clean isolated
consumer environment imports Core from the actual Git release rather than the
local editable package. Independent downloaded-artifact checks and current
released-consumer feature tests are separate from producer proof. Actual published
and native app images must also prove the released Git source before readiness.

The actual released-Git consumer passes110 focused cases without database skips.
Independent downloaded wheel/archive rebuilds, external installs, OCR and migrations
pass6 cases using the producer commit epoch1794795899. The initial independent
rebuild used the generic default epoch and failed only on tar timestamps; all
members, contents and modes matched. Failed evidence is retained separately.
All21 native Robot dry runs and706 maintained documentation links pass. The
consumer lock changes only the application/Core versions and immutable Core source;
other dependency bytes and published Core files remain unchanged. Current consumer
full/native/image acceptance remains a separate outstanding gate.


## Existing-API attachment recovery

The installed binary attachment endpoint still returns500. A subsequent actual
C0 adapter probe over verified public HTTPS recovers the synthetic supported
attachment through GET `/me/messages/forward?includeAttachments=true`. This reads
a template only; source inspection confirms a read-only mailbox open, and the
installed probe confirms the message remains unread. Exact decoded bytes match
the synthetic fixture; the unsupported attachment remains explicitly reported.
No source product changes, draft saves, sends or C0 publications occur.

The fallback requires the original Message-ID and folder, and a unique matching
filename, normalized MIME type and content ID in both original and template
responses. Missing identifiers, duplicate descriptors and authorization denials
fail closed. Only source unavailability can trigger the extra read. Normal
responses remain bounded to10MiB; the template wrapper may use20MiB and each
decoded attachment must fit10MiB. Reported source sizes count MIME transfer
octets: the installed fixture reports46 for32 decoded bytes. They are never
used as decoded-content identity. Templates exceeding the bound remain visible
as attachment failures. The focused source-adapter suite passes29 cases, including
ambiguity, denial, invalid encoding and decoded-size limits. This app-only change
leaves the published Core package bytes unchanged and requires its own exact
consumer full/native evidence.


A released-Core PostgreSQL workload test provisions six never-signed-in users,
rotates at most five owners per pass, recreates the runner after every pass and
adds messages during pagination. All72 distinct messages are staged in their
respective spaces and every owner completes inventory within eight passes
(40 minutes at the configured timer interval); no C0 login accounts are fabricated.
This proves bounded restart/fairness behavior at that synthetic workload, not
performance or daily coverage for an unspecified larger installation.
