# C0 roadmap

## Self-service Read and space audiences — implementation candidate

Based on original main6e9554c. New HTTPS metadata clients use verified first-party
sign-in and explicit Read consent without administrator review. The discovery
switch is removed for both new and upgraded/restored installations. Explicit
user blocks, disabled applications, metadata review, scopes and credential
bindings remain enforced. Space audiences add authenticated baseline Read with
revisioned Admin changes; existing protected spaces remain restricted. The
whole readable space is included, and tightening revokes affected credentials.

Development evidence: original-main authentication baseline56 passes in an
independent database; focused review108 and final focused101 pass. Node24 website
checks pass28 unit cases and46 interactions; four audience cases also pass after
draft guards with inspected phone/desktop theme screenshots. Signed HTTPS browser
acceptance passes12, including Reader/Admin self-service Read issuance. Native UI
controllers28, action schemas and745 documentation links pass. Final fast checks
pass1738 locally. These counts overlap and are not an aggregate acceptance total.

Draft PR130 sourceb76220b's fast43188463675 fails three native-fixture expectations:
two retained Core0.47 bindings and one missing mocked SDK cleanup operation. The
successor corrects them without changing or cancelling the failed evidence.
The broad development run retains3333 passes/35 failures/three errors. Its
successors correct stale approval/plugin/schema expectations, seed historical
layouts with the installed released predecessor's space authorization, and avoid
PYTHONPATH contamination of independent predecessor processes. The OCR/PDF and
independent packaging container rerun passes41; migration reruns pass31 plus the
three corrected populated compilation predecessors. The automatic-preparation
queue guard passes80 database cases; updated frontend interactions pass47 and
native fixture/controller regressions pass53. Unchanged-authority policy metadata refresh preserves audience drafts and their original revisions; the four browser audience cases include stale-save rejection. These are overlapping development
checks, not an exact-source full/native acceptance claim.

Native acceptance now requires real first-use Read issuance through the fixed
public HTTPS metadata fixture, Reader access to an authenticated-reader space,
explicit additional Write review without changing the Reader role, and audience
preservation after restart. Full exact-source producer, native and released
consumer acceptance remains required.

Producer development and regression validation are in progress. Core publication,
released-consumer adoption, exact-source full/native acceptance and upstream
review remain required. No live deployment or existing-space audience change is claimed.

## Native OAuth accepted deployment

The separately authorized 12 November update installs app **0.64.0**, released
Core **0.46.0**, schema **0037_embedding_context**, source
`a106f188d362fa02574972662f84bb3fc93774af`. This is the installed baseline;
later producer work and Git-only documentation markers retain separate acceptance
and deployment gates.

[PR115](https://github.com/Stell0/ns8-czero/pull/115) regularly merges the released
consumer as `505b8ee`. [PR113](https://github.com/Stell0/ns8-czero/pull/113) repairs
cumulative-role browser assertions and the Debian image URL, then regularly
merges as `a106f18`. Its accepted `5af2aba` candidate and that main source have
identical Git trees. Full
[43117140826](https://github.com/Stell0/ns8-czero/actions/runs/43117140826), the
actual C0 gate, canonical publication, independent downloaded native/artifact
inspection and six fresh registry alias reads pass. Evidence includes 3294
Python/PostgreSQL/packaging cases without skips, 43 document-browser cases,
40 website-browser cases, 28 Vue unit cases and 21 Robot dry runs. Actual native
reports pass Debian upgrade 21 and Rocky installation 26/three expected skips,
all eight browser/privacy workflows, 30 accessibility contexts, five scan/SBOM
pairs and zero OAuth-query candidates. The dated Debian image uses its published
SHA512 verification. Retain earlier DNS/artifact-outage and cloud-image404 runs;
optional PR screenshot publication403 remains nonblocking.

Freeze the installed tag `ci-a106f188d362fa02574972662f84bb3fc93774af-43117140826-1`
and these identities as the next genuine upgrade predecessor:

| Image | Installed digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:ef32840cf6b92730f80decb8c45ac3b1d0076bb7ed0623b5b7fb5869b8820714` |
| `ghcr.io/stell0/czero-app` | `sha256:05e37d34478b14f6d5ac24f1c72a88f9777aa64270940d8007a537fcdb681185` |
| `ghcr.io/stell0/czero-postgres` | `sha256:bee0fac158c41ae862a78464a94a6a950704e27de38a9b3213b5512d1b4abd00` |

The actual published, native and installed app images verify released Git Core
`d8ae98ca1a60e34803fa7ed04ea998c1f9dbb33a` from immutable
[Core0.46.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.46.0),
schema0037 and the loopback matcher, with no NS8 SDK or local-Core fallback.
The one existing embedding profile remains legacy; extraction/reindex counts
stay unchanged. Core0.47/schema0038 cross-space references remain separate
producer work and are absent from this installed source.

The genuine inspected predecessor is app0.63.0/Core0.45.0/schema0036, source
`1db37f409af756212dc005d160302d01eff23098`, tag
`ci-1db37f409af756212dc005d160302d01eff23098-42437861637-1`. Keep its images
and earlier accepted installation evidence, including the historical
app0.61/Core0.42 record:

| Image | Genuine predecessor digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:369d81853dc99d3710ea733fcb5d010256d699421728660ede4c9d15b74c3967` |
| `ghcr.io/stell0/czero-app` | `sha256:9ee56e8f67564b1228e1abcb427a5ee25bbd01303058f1da11365288c387687b` |
| `ghcr.io/stell0/czero-postgres` | `sha256:0b91cd3e1e7da919bb0746c3f3d412c739b275b3e0de50b52ec0aecfe5123fad` |

Supported C0-only backup and full Restic read-data verification pass before
update. All 16 current backup definitions are restored exactly. Read-only
preflight verifies 6587 complete sources, 451 multipart parents and no pending
source replacements. A fresh 64-table/1,315,729-row snapshot binds preservation:
55 tables retain exact row hashes; API-key authority matches the verified backup
and only one last-used timestamp advances from live reads. This comparison uses
offline selected-table extraction and parameterized read-only SQL, with no
production restore. Schema revision, append-only job history, scheduler clocks
and documented renewal fields receive separate checks. Knowledge cursors/events,
credentials, settings, grants, schedules and all 11 unrelated module identities
and flag sets are preserved. The source-original store remains empty.

The supported immutable-digest update and `node/1/restart-module` pass. Actual
installed image/Core identities, trusted HTTPS app/Core/schema readiness and all
C0 units pass afterward. Fresh MCP discovery matches 121 capability operations
under the existing key's scopes; the existing OAuth connection returns the same
account before update, after update and after restart. Bounded root application
journals contain 55 entries, three real health and 14 MCP positive controls, and
zero credential/query/traceback candidates. The owned documentation-job lock is
released; its files and definitions are retained. Private data, credentials,
snapshot identities and raw operational evidence remain outside Git.

Approved portless HTTP loopback callbacks accept the requested native port;
explicit ports, host/path/resource, consent and exact token redemption retain
their checks. Person roles use cumulative labels while application scopes remain
independent. Actual end-user Claude Code approval/consent still needs a fresh
interactive flow; native fixtures and signed HTTP tests do not establish that
vendor-client acceptance. Broader packaged-skill/scheduled-client gates, Core0.47
adoption and a stable NS8 module release remain separate. The interactive-browser
and container CPU-quota waivers are unchanged.

## Secure cross-space references

The operator-selected [implementation contract](docs/cross-space-references-plan.md)
starts at original main `bdb928e62a057309d7822282fd7c505303d3bbfb`.
M0 preserves the contract; M1 adds shared batch authorization; M2 adds outgoing
reference storage and Core operations; M3 supplies REST/MCP and agent guidance.
Core publication, released consumer adoption and live deployment retain separate
acceptance gates. No browser panels or live changes are included.

### Released Core0.47 consumer acceptance

App **0.65.0**, independently released Core **0.47.0** and schema
**0038_cross_space_references** complete M0–M4. This is source and publication
acceptance. The installed baseline remains app 0.64/Core 0.46 at `a106f18`. Live
deployment and browser panels remain separate M5 work.

Producer [PR119](https://github.com/Stell0/ns8-czero/pull/119) regularly merges as
`08e979c`. Exact producer full 43118191778, actual main full 43125359808,
independent downloaded native/privacy/scan audits, full promotion and six fresh
canonical registry reads pass. Immutable Core tag `core-v0.47.0` stays at
`884ff312` with package tree `038af088d8155be709ff9d7a839b7f0155f28528`. Publisher
43125626421 and independently downloaded wheel/archive checksums pass. Retain the
frozen producer, successor, failed query-plan/fixture/environment runs and earlier
native evidence.

Consumer [PR128](https://github.com/Stell0/ns8-czero/pull/128):
`8167f12cc663445bba4f70efbc8c9ce2753a3936`, regular merge
`0daf8a0ef6bb9c570c139e60ae6351f46c17e19a`, exact full
[43141979583](https://github.com/Stell0/ns8-czero/actions/runs/43141979583) and
actual main full
[43148755615](https://github.com/Stell0/ns8-czero/actions/runs/43148755615). HEAD
and merge trees match. Actual published/native app images select released Core
from the frozen Git lock, verify its immutable `884ff312` identity and schema
0038, bind all three reference routes and contain no NS8 SDK. The final native
predecessor is the separately accepted app 0.64, Core 0.46/schema 0037 `a106f18`
installation, using all three verified immutable images. Reference rows and
non-resurrecting replay receipts survive the native clean restore on both
distributions.

Exact-source full checks pass 3379 Python/PostgreSQL/packaging, 43
document-browser, 40 website-browser, 28 Vue unit cases and 21 Robot dry runs.
Independent downloaded audits pass Debian 21 and Rocky 26/three expected skips,
all eight native browser/privacy workflows, 30 accessibility contexts, five
scan/SBOM pairs, three query-audited artifacts and zero OAuth-query candidates.
Exact-source full promotion passes. All six fresh main/latest alias reads match
these accepted immutable identities. The source tag is
`ci-0daf8a0ef6bb9c570c139e60ae6351f46c17e19a-43148755615-1`.

| Image | Accepted publication digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:56dfa3144f5fbc8c8ee984f02261f98e48da15c8310d2d41e57f7bb7ec5aff69` |
| `ghcr.io/stell0/czero-app` | `sha256:0a45ef93c9c3fa9b1cd39373c64366dad32448fc754ab1291b3d3ed83769e2b3` |
| `ghcr.io/stell0/czero-postgres` | `sha256:ed2278da16eca349c6fa019c4a5f03426dc04f06c76f59efee4851016b8c2e91` |

The complete actual released-Git suite also passes 3365 cases without database
skips at frozen `c1aba893`; app/Core code is byte-identical to the final consumer.
The identical final file tree passes 440 affected released-Git cases and 9
documentation tests; the exact source also passes 225 source/policy/documentation
cases, 21 Robot dry runs, 743 local links and actual Renovate 44.161.0 patch/minor
bounds. All other locked runtime versions remain frozen.

The same frozen benchmark driver completes 30 Option-A independent-resolution
groups with 20 warmups, 200 measured calls, three repetitions and concurrency 1/5.
For 100 mixed targets/ten spaces its median-repetition P95 is 796.9/2219.4 ms,
with 2100 SQL statements. These reads fetch complete resources; the new reference
list returns summaries, so they are workload controls rather than identical
payload comparisons. The new active matrix has 1782 groups, max P95 60.6 ms,
constant session/OAuth/key SQL counts 15/25/14 and 377218 peak allocated bytes.
All 72 same-space control comparisons pass; max P95 increase 2.1 ms. Frozen
`884ff312` missing/sparse fixtures pass 36 groups each, with max P95 31.2/102.7 ms
and no post-revocation items, deadlocks or timeouts.

The frozen acbfdfb actual released-Git signed REST diagnostic interleaves hidden,
missing-resource and missing-space creates: 20 warmups and 200 calls per variant
in each of three repetitions. All return identical 404 bodies and no-store; P95
spans 21.7–22.4 ms. This is a gross local timing observation, not constant-time or
production latency proof. The existing connected account profile read still works;
its unchanged installed catalog correctly does not advertise references. No
connection identity, consent, live source, data, schedules or installed image is
changed by this acceptance. No stable NS8 module release is claimed.

The following candidate checkpoints are retained as history; this accepted
checkpoint supersedes their pending source/publication gates.

### Released Core0.47 consumer candidate

[PR119](https://github.com/Stell0/ns8-czero/pull/119) regularly merges as
`08e979c4ae285bed03953cf58c6a0a63ebc8888c`; its tested producer
`884ff312c18fbc18bb613137bbb6ced17df6cfb0` passes exact full
[43118191778](https://github.com/Stell0/ns8-czero/actions/runs/43118191778):
3365 Python/PostgreSQL/packaging,43 live browser,40 website browser,28 Vue unit
cases and21 Robot dry runs. Exact-source full promotion and independent downloaded
artifact checks pass: Debian21,Rocky26/three expected skips,all eight native
browser/privacy workflows,five scan/SBOM pairs and zero OAuth-query candidates.
The regular merge retains exactly the tested tree. The previous candidate and
failed private evidence remain frozen. Basea106f18 full43117140826 also passes.

[Core0.47.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.47.0) is
immutably published from that producer by
[43125626421](https://github.com/Stell0/ns8-czero/actions/runs/43125626421).
Downloaded checksums and independent wheel/archive inspection pass: wheel
`902ad47cba16e7337d0f6826292ce8526ba97ab5341aff5e540e4779337f0d63`,
archive `c303ee19a7763e98fd60dbd6a27405b90f81958f7bc5c6bd4f753f1d6041fefc`.
The assets include the standalone service,license and schema0038. Publisher
external installation/recovery checks pass all6 cases.

App0.65 separately adopts its Git tag/lock at the immutable producer commit,
with `>=0.47.0,<0.48.0` and matching patch-only updater bounds. Other dependency
versions remain frozen. The Core package tree is unchanged, so reference image
publication must select released Core and verify its actual Git identity and
schema0038 inside the published/native app image. Extend that runtime probe to
bind all three reference routes without a database or model execution.
Local actual released-Git validation passes148 focused authorization, reference,
transport, scope, source/lock, release-policy and documentation cases,728 local
links and21 Robot dry runs. The runtime probe binds schema0038 and all three
reference routes without a database/model; its Git identity matches884ff312.
The reference source selector returns released, and every frozen runtime version
is preserved. The registered runtime probe changes deliberately; registry and
unresolved comparison state remain unchanged.
The first frozen consumer8cfcd37/run43127377557 rejects a stale hardcoded
Core0.46 versioning fixture. The successor derives each consumer's active tag
from its manifest and exercises actual Renovate44.161.0 patch/minor bounds.
The first manual full released run lacks its frontend build; preserve its page/
font failures and repeat with the compiled frontend. The corrected successor
passes211 actual released-Git page/font, reference, authorization, SDK and
source/lock tests, plus the native Renovate44.161.0 bounds check. Runtime dependencies,
Core bytes and acceptance limits remain unchanged.
Latest original main1e99d7d records the independently authorized accepted
app0.64/Core0.46/schema0037 installation. Preserve that deployment record and
all app0.63/Core0.45 frozen feature evidence. The new consumer successor uses
the accepted a106f18 installation's three immutable digests as its genuine
native predecessor, exercising actual schema0037→0038 update/restore. It adds
no live deployment authority. Core bytes, lock, app code and prior acceptance
runs remain unchanged. The successor passes217 actual released-Git reference,
page/font, SDK, source, predecessor and release-policy cases,21 Robot dry runs,
730 documentation links and the real Renovate44.161.0 bounds check. Independent
registry reads bind all three predecessor digests and source labels to a106f18.
Fresh exact-source full/native acceptance remains required.
Original main8f265dd then merges the separate CI/developer-guidance change.
Preserve acbfdfb/run43134856085 and its running evidence; its full Python suite
and all21 genuine0.64 Debian upgrade cases pass. A new isolated consumer
successor retains the complete streamlined instructions and managed registry,
including explicit instruction review before PR readiness. Its app/Core code,
consumer tag/lock, versioning fix and genuine0.64 predecessor fixture exactly
match acbfdfb. The Core package tree remains identical to published core-v0.47.0.
Repeat affected policy, reference, package and exact-source full/native checks;
no frozen history, image identity or acceptance limit is changed.
Migration0038 adds an empty reference table; no existing content, grants, scopes,
connections or schedules are changed. Full released-consumer/native/image and
main publication gates remain required. No installed baseline changes, browser
reference panels, live upgrade or schedule activation are included.

### Producer checkpoints and measured evidence

Implementation candidate: Core0.47/schema0038 adds immutable typed references,
current summaries, actor/source-scoped payload-free receipts and guarded deletion.
Plugin1.10 and guidance7 describe navigation and separate publication authority.
The transport is capability-gated: actual frozen Core0.44 consumer startup/profile
read succeeds and unsupported operations stay absent. A successor on original
main505b8ee preserves the new Core0.46 tag/lock, app0.64 and genuine native
predecessor. The Core0.47 feature tree is identical to frozen dab4140; repeat
affected native checks on the successor. Its231 affected PostgreSQL/security/
transport/catalog/package-guidance cases pass, as do56 documentation/source-pin/
release-policy cases and21 Robot dry runs. Actual frozen Core0.46 startup/profile
read, unsupported-tool omission and immutable Git/schema/loopback probes pass.
No dependency range, tag/lock or genuine predecessor identity is replaced by
this feature; producer/native and released-consumer gates remain distinct.

Executed focused proof:58 PostgreSQL Core/authorization cases (all25 endpoint
pairs, migration0037→0038 preserving rows/constraints, key restrictions, revocation
waits in both orders, explicit READ COMMITTED under a repeatable-read default,
byte-budget pagination and endpoint-delete serialization);10 signed REST/current+legacy SDK cases;
6 exact native-probe HTTP regressions;67 catalog/guidance/archive/runtime-audit
cases. The parser-equipped disposable container passes all6 wheel/source package
checks, including installed references, repeated migrations and OCR. Host package
OCR failures remain private. Node settings28, schema patterns,21 Robot dry runs
and maintained documentation checks pass.

The benchmark driver includes a100000-edge corpus and explicit matrix controls.
An initial5-sample diagnostic finds constant SQL counts over1/100 references and
1/10 target spaces for sessions/OAuth/keys, max P95 about13ms,342154 peak allocated
bytes and25616 returned bytes. These are diagnostics, not accepted benchmark gates.
A later20-sample dense-source diagnostic covers100000 outgoing references with
all three credentials, visibility modes and concurrency1/5: maximum P95 about57ms,
constant SQL counts,374654 peak allocated bytes, and five admitted readers complete
before revocation. The original broad join exhausts64MiB PostgreSQL shared memory;
its failure is retained. The revised parameterized lateral UNION/keyset plan avoids
whole-endpoint hash scans without changing limits. Removing explicit READ COMMITTED
reproduces stale-key admission; restoring it passes the barrier regression.
Space-wide permissions cannot yield partial resource authorization in one selected
space; half-visibility measurements must report actual visible cardinality.
The frozen dab4140 active benchmark completes1782 groups with20 warmups,
200 measured calls and three repetitions at concurrency1/5. Maximum P50 is45.5ms,
P95 is60.6ms, peak allocated memory377218 bytes and response25870 bytes. Session/
OAuth/key SQL counts remain15/25/14 throughout. Five admitted readers complete
before revocation (149.2ms wait/commit), with no post-revocation target items,
deadlocks or timeouts; the dense indexed query plan executes in4.9ms.
Matched original bdb928e and candidate19ad5ef same-space controls pass all72
repetition comparisons; maximum P95 increase is2.1ms, below the5ms allowance.
Separate archived/deleted and0.1%-visible100000-edge fixtures also pass their
measured gates. Bound fixture deletion into500-row statements rather than
relaxing the existing deadline. Sparse selection uses one readable target space
among ten selected spaces and exactly100 readable references among100000.

Latest base505b8ee actual full local checks pass3294 cases and43 real browser
cases; Rocky passes. Its Debian job fails because the moving genericcloud URL
returns404. Preserve this failure. The candidate pins the dated official image
whose SHA512 is identical to the earlier accepted VM, keeping checksum checks.
The first feature native run exposes stale browser workflow expectations; the
Reader display allowlist and both browser suites now cover navigation. All7
real guidance browser cases pass across roles, light/dark, desktop/phone and
keyboard controls. Node24 frontend checks pass28 tests, lint, formatting, types
and build; the policy21 Robot dry runs pass. Retained reference/receipt seed and
verification pass all6 external package cases and a real PostgreSQL dump/restore.

Per-target-resolution comparison and final exact-source full/native/browser/
image/artifact/merge proof remain separate gates. Do not publish Core, adopt a
new consumer lock or deploy on focused or diagnostic evidence alone.

The next preserved successor starts at original main
`a106f188d362fa02574972662f84bb3fc93774af` after the cumulative role-label merge.
It retains the upstream labels, their native assertions and the identical dated
Debian image pin. The original base and latest base have identical released
Core0.46 package trees; the reference Core0.47 tree remains unchanged. Repeat
full/native and browser verification on this source before promotion.

## Released Core0.46 — native OAuth consumer candidate

Start at latest original main `bdb928e`, preserving the accepted producer
`d8ae98c` and its immutable images. [PR114](https://github.com/Stell0/ns8-czero/pull/114)
passes exact full [43035611008](https://github.com/Stell0/ns8-czero/actions/runs/43035611008)
after retrying external DNS/API failures: 3294 Python/PostgreSQL/packaging,
43 document-browser,32 website-browser and28 Vue unit cases. Independent
artifact verification passes Debian21, Rocky26/three expected skips, all eight
native browser workflows, five scan/SBOM pairs and zero OAuth-query candidates.
The required C0 merge gate passes; optional screenshot publication remains
nonblocking. Main [43090674220](https://github.com/Stell0/ns8-czero/actions/runs/43090674220)
fails during Debian cloud-image download with HTTP404; retain that failed
main evidence as a separate source/publication gate.

Immutable [Core0.46.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.46.0)
is published from that accepted producer by
[43091209705](https://github.com/Stell0/ns8-czero/actions/runs/43091209705).
Downloaded release checksums pass: wheel
`d75f4d3ae48c13036ea20b683b746e69757a90265bcd6391b4754491602c99ae`,
archive `4e96ab9af0b2331c8a914331c4fb7a055159b5ae75f869337718eb99fa90776a`.
Metadata, license, schema0037 and the loopback matcher are present in the assets.
The app0.64 candidate adopts its Git tag/lock with
`>=0.46.0,<0.47.0` and matching patch-only updater bounds. Keep the Core package
tree unchanged. Verify the actual released Git source, schema0037 and loopback
matcher in the published app image. Migration0037 defaults existing embedding
profiles to legacy input; adoption does not enable contextual inputs or queue
reindexing. Existing roles, scopes, callbacks, sources and schedules retain
their contracts.

Native acceptance must upgrade the genuine app0.63/Core0.45/schema0036
predecessor `1db37f4` using all three frozen image digests, preserve content and
grants, and exercise clean backup/restore. Retain the older migration fixtures.
Run the OAuth regressions with released Core and require full consumer/native,
current-source review/merge and actual main publication checks. Live update
remains separately authorized and requires supported backup, preservation,
readiness, client checks, restart and positive-control journald audits. Neither
a published Core nor producer acceptance establishes consumer deployment.

Local released-Git validation passes169 focused authorization, callback,
migration and source/lock cases, plus21 Robot dry runs. The installed package's
immutable Git identity and loopback behavior pass the runtime probe, and source
selection returns released. The lock changes only the app/Core versions and
Core tag/commit. Actual Renovate44.161.0 bounds pass on Node24; maintained
documentation checks pass723 local links. Full released-Git Python validation
passes3294 cases with no skips. [PR115](https://github.com/Stell0/ns8-czero/pull/115)
passes full [43093793504](https://github.com/Stell0/ns8-czero/actions/runs/43093793504)
attempt2 after retrying its failed artifact-download job following the GitHub
Actions outage. The actual C0 merge gate and independent native/artifact audit
pass: Debian21, Rocky26/three expected skips, all eight browser workflows,
five scan/SBOM pairs and zero OAuth-query candidates. The actual published app
image contains released Git Core0.46.0 at `d8ae98c`, schema0037 and the matcher.
Regular merge `505b8ee` preserves the candidate; its main
[43105029868](https://github.com/Stell0/ns8-czero/actions/runs/43105029868)
hits the same Debian cloud-image404. This is the historical consumer checkpoint;
the accepted deployment is recorded in [the current baseline](#native-oauth-accepted-deployment).


## Native OAuth callback repair

Permit a requested port only when an approved callback is a portless HTTP
loopback URL (`localhost`, `127.0.0.1` or `[::1]`). Keep the exact host/path,
explicit-port registrations, HTTPS callbacks and code-exchange callback binding.
Use one Core matcher for approval, onboarding, consent and code issuance; the
HTTP adapter projects only that validated request callback into the SDK's
request-local descriptor. Preserve current roles, scopes, metadata reviews and
all existing authority/revision checks. No schema or consumer lock change.

Acceptance: reproduce the rejected approval, test actual PostgreSQL and signed
HTTP approval/consent/token exchange with changing loopback ports, reject host,
path, scheme, port, PKCE and scope substitutions, and exercise the administrator
dialog in Chromium. Run base/candidate checks under the CI risk policy and retain
full Debian/Rocky native acceptance before merge. Core publication, released app
adoption and live deployment remain separate; no live permissions are changed.

Executed local evidence: exact original main `4af1d703` has verified full
acceptance `42609484240`. Six new signed-HTTP cases fail with approval409 before
the repair and pass afterward. The affected authentication selection passes209
cases; released Core0.44 compatibility passes84. Fast Python checks pass1739,
native JavaScript28, frontend unit checks28 and Robot dry runs21. All11 affected
Chromium workflows pass, including light/dark phone/desktop keyboard approval.
Frontend lint/format/type/build and maintained documentation checks pass.
The host package run passes12 cases and fails2 extraction probes because its
OCR binary is absent; retain that evidence and rerun unchanged checks in the
separate parser-equipped disposable container. Full native CI remains required.
## Administration role wording

Repair acceptance starts on current original main `505b8ee`, preserving the
frozen PR113 commit `1a866a2`, the OAuth repair and released Core0.46 adoption.
Update every person-role/protected-space browser selector to the cumulative
labels, while retaining independent application-scope checkboxes and all
existing permission, revision, CSRF and recovery checks. Cover saved role
labels, unchanged role values, English/Italian, light/dark and phone/desktop
keyboard/layout workflows. Require full native CI, actual merge gates and
merged-main publication before the authorized dedicated update. Stop on a new
GitHub-outage CI failure; preserve failed evidence and do not bypass checks.

The moving Debian13 cloud-image URL returns404 during the current main runs.
Use the shared runner's supported URL override for the official dated
20261103-2651 Debian13 image, whose adjacent SHA512SUMS is available. Preserve
the checksum verification, scenarios, timeouts and full native requirements.

The clarification candidate starts from original main `4af1d70`. English and
Italian person-role selectors and saved summaries show cumulative access levels;
protected-space Editor choices use the same Read and write label. The selectors
save the existing role values, while application consent keeps independent scope
labels. Frontend lint/format/types/build and 28 unit checks pass. Eight isolated
browser contexts pass English/Italian, light/dark and phone/desktop selection,
save/readback, keyboard and overflow checks using synthetic API replies. Full
native acceptance remains the automatic CI gate for these Vue components.

## Retrieval evidence producer candidate

The isolated candidate starts at original main `6bb8cea`, with Core0.46/schema0037
and plugin1.9. It normalizes bounded search whitespace, retains one distinct
semantic passage during document fusion, and adds opt-in versioned contextual
embedding inputs with transactional invalidation and complete-coverage checks.
See [contracts and validation](docs/retrieval-evidence.md). The released Core0.44
consumer lock, installed runtime and accepted image identities remain frozen.
No Core publication, consumer adoption, live indexing or deployment is implied.

## Document BM25 — released Core, consumer adoption

[PR99](https://github.com/Stell0/ns8-czero/pull/99) regularly merged as
`1783cf6a1ad92edb1016488a87bd1e9769f90198`. Accepted producer
`bb882504fb5ab3b94f10bd1d286b06fa81b004ea` is based on original main
`b8ec5bfe8883168234535c4113f2e52c1b1d887e`, preserving M4. Core0.44/schema0036
adds body-free document lengths/term frequencies, English/Italian normalization,
ordinary OR matching and document BM25. Exact phrases/operators and structured
filters remain constrained. Citations retain their bodies, hashes and offsets;
source-only responses retain their citation-list shape. Hybrid fuses document
rankings. Plugin1.7.1 documents optional ranker metadata without changing scopes.

Exact producer full runs
[42402100986](https://github.com/Stell0/ns8-czero/actions/runs/42402100986) and
[42402272499](https://github.com/Stell0/ns8-czero/actions/runs/42402272499)
pass, including the actual C0 merge gate: 3,058 Python/PostgreSQL/packaging,
40 document-browser, 27 website-browser,28 Vue and 28 Node cases. Independent
native/artifact audit passes Debian 21, Rocky 26/three expected skips, eight
reader workflows, 30 accessibility contexts, five scan/SBOM pairs and all three
installed image identities. Optional screenshot publication failed with 403;
required native evidence and workflows passed. The local full run started
before compiled website assets existed and failed 18 route/font cases; after
building assets all 141 app cases pass. Clean CI supplies the full-suite proof.

[Core0.44.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.44.0) is
immutably published at `bb882504fb5ab3b94f10bd1d286b06fa81b004ea` by
[publisher42407305955](https://github.com/Stell0/ns8-czero/actions/runs/42407305955)
after exact-source full promotion verification. Downloaded release checksums pass:
wheel `91bf421a1cdc713504063835a8582923c168163f9727f19fc170fc40b8780f5d`,
archive `5efcfdc45894b5a26a9489d549db5ffde23ca40eca71fb9c1db78149fb4e9352`.
App0.62 adopts its immutable tag/lock with patch-only updater bounds through
[PR100](https://github.com/Stell0/ns8-czero/pull/100), regularly merged as
`59fcc3cf6b89799ba121a50e5721ac45a3e36df5`. Its tracked tree exactly matches
accepted consumer `694deda39285028a0af16d4aea474af5f9099f76`. Core package bytes
remain identical to the release. Native upgrade uses the recorded
app0.61/Core0.42/schema0034 predecessor at827fbde; producer native evidence
retains the older 0.54 history-to-latest-only migration proof.

Consumer [full42408184499](https://github.com/Stell0/ns8-czero/actions/runs/42408184499),
actual C0 merge gate, exact-source full promotion proof and independent downloaded
artifact audit pass. Both local and CI runs pass all 3,058 Python/PostgreSQL/packaging
cases and 40 document-browser cases. Debian 21 and Rocky 26/three expected skips,
eight reader workflows, 30 accessibility contexts, five scan/SBOM pairs and all
three installed image identities pass with zero OAuth-query candidates. Optional
screenshot publication failed; required native/artifact checks and the overall
workflow passed. The actual published app image verifies Core's released Git
commit/schema, and independent registry reads verify all three digests and
module sibling references. No database tests were skipped.

Freeze consumer tag
`ci-694deda39285028a0af16d4aea474af5f9099f76-42408184499-1`:

| Image | Accepted consumer digest |
| --- | --- |
| Module | `sha256:5c5c817347ad453e2ef09bbbf6d96e64602b2c47d9fc52be1df1b7ce6eb6412d` |
| App | `sha256:6189f4121443feac6b747b2d13bc9fc0442e9d6e542397fbcce481a1af8922dc` |
| PostgreSQL | `sha256:64ee9785eb58ea9e6f4dd0334970c6d1b08d9c5c962a8a78eda2a1efba53c494` |

Producer-main [42407246728](https://github.com/Stell0/ns8-czero/actions/runs/42407246728)
passes full/native/browser/artifact gates, canonical publication, independent
artifact audit, exact-source promotion and six fresh registry alias reads.
Consumer-main [42413222963](https://github.com/Stell0/ns8-czero/actions/runs/42413222963)
also passes full/native/browser/artifact gates and canonical publication.
Independent downloaded reports confirm Debian 21, Rocky 26/three expected skips,
eight reader workflows, 30 accessibility contexts, five scan/SBOM pairs, all
three installed identities and zero OAuth-query candidates. Actual main passes
3,058 Python/PostgreSQL/packaging and 40 browser cases; the published app image
verifies the released Git Core. Exact-source full promotion proof and six fresh
`main`/`latest` registry reads pass. Freeze the accepted main tag and identities;
this documentation closeout does not replace or deploy production images.

`ci-59fcc3cf6b89799ba121a50e5721ac45a3e36df5-42413222963-1`:

| Image | Accepted main digest |
| --- | --- |
| Module | `sha256:94c341a2cd9217cbe6c7a2637000d4a8f58c14e5a42f0b313bfdd0a8b0b8e13e` |
| App | `sha256:92222434751765ad020bb06f4e7093d514474b033e4192e153260f5d02b872cd` |
| PostgreSQL | `sha256:4629070c3acba1995bfb42af1db253011efc9266648d0bf4723469fc15de3f1a` |

Final matched current-base measurements freeze lexical, retrieval and citation
helpers from b8ec5bf for the baseline. SciFact's 5,183 documents/300 queries score
nDCG@10 0.6782 and Recall@10 0.8073 against 0.3098/0.3372; empty results fall
from 156 to 6. P95 falls from 149.0ms to 91.6ms, passing the unchanged 1.5× ceiling.
Returned-document recall is 0.8802, oracle nDCG@10 is 0.8819 and mean distinct
documents is 48.68. Initial backfill takes 33.68s and occupies 104,652,800 bytes;
final reruns' idempotent migration timing is not indexing time. SciFact was
already development evidence. The original 0.3101 differs slightly because of
fresh UUID ties in the recreated baseline.

NFCorpus's 3,633 documents/323 queries score 0.3206/0.1538 against 0.2365/0.1024;
empty results fall 82→18 and P95 128.7→56.8ms. Its first holdout run froze 4595054
before evaluation; subsequent runs are exposed-set checks. Frozen semantic
candidate arrays give hybrid nDCG 0.7388 against baseline 0.7198 and semantic-only
0.7133, passing the 0.01 guardrail. Recall is 0.8536/0.8592/0.8559. All 300 queries
and before/after corpus checks completed before a cleanup-only client error;
an incomplete later probe is excluded. This ranking audit does not establish
candidate provider latency or provider-profile stability throughout capture.

The approved documentation copy contains 251 current bodies and metadata with 50
unchanged questions. Fourteen bindings changed; every original labelled passage
validates. For 45 positive-label queries nDCG rises 0.5250→0.6631 and Recall
0.6444→0.8407; all 50 empty results fall 11→0 and P95 148.0→115.9ms. Answerable
query evidence coverage moves 0.7000→0.6875; complete evidence stays 0.6750.
Broader weak candidates increase wrong-product results, so relevance does not
establish answerability. Labels, queries, thresholds and grants are unchanged.

Preserve earlier candidates ddb9421, 4595054, 8090ab6, f1c4796, fbae9a2 and all failed
runs. In particular fbae9a2 fails SciFact latency 286.0ms versus 149.4ms (1.91×).
The accepted successor batches citations and current-generation checks, reducing
round trips without changing document ranks or citation payloads. Early batch
timings that shared its citation helper with the baseline remain diagnostic;
the final comparison freezes all three baseline modules. See
[retrieval contracts and measurements](docs/retrieval-benchmark.md).

The owned private plugin received a content-only patch preserving its connection
identity, scopes and other files. Refreshed account/space discovery, authorized
search and exact citation reads pass against the installed runtime, which still
reports its existing lexical strategy. This does not claim live BM25 acceptance.
Production deployment remains separately authorized; this task leaves installed
images, credentials, access grants and schedules unchanged.


<a id="openai-system-one-scoring--current-base-successor"></a>

## OpenAI System One scoring — accepted delivery

Based on original main `c16eb49f0cfa3fb428d96dfff42222862f809289`, preserving
accepted M3 contracts/tests, schema0034 and managed-file/dependency-lock state.
The frozen previous-base candidate `c5809e3dd4a2558953880d17ce1c7639823e35b3`
and full42375273513 remain previous-base evidence:2959 Python/PostgreSQL/packaging,
40 document-browser,27 website-browser cases and Debian native21 pass. Its full
run remains uncancelled. It does not establish acceptance on this new base.

Replace JEV/Kev with OpenAI Decisions named predicate probabilities, retaining
search interfaces, configuration format, authorization, provider bounds and
ordinary-ranking fallback. Empty candidates complete scoring without I/O.
Core0.42 uses a separate immutable release identity from M3's0.41 candidate.
Scoring adds no migration or runtime dependency; the base's schema0034 publication
metadata migration is covered by genuine upgrade/restore and consumer acceptance.
Existing scorer descriptors require explicit endpoint/model/key replacement;
empty native forms suggest OpenAI. Compilation maintenance stays off and no project,
compiler, ingestion or external schedule is initialized.

Acceptance covers complete named answers, malformed/refused responses, bounds,
TLS/deadlines, rerank/filter/empty results, in-flight revocation, REST/MCP, native
settings and disposable HTTPS/update/restore/browser fixtures. Exact current-base
baseline/candidate and full/native/artifact gates remain required. Publication,
released consumer tag/range/lock adoption and dedicated deployment are separate.
After operator key configuration, reuse the existing full SciFact corpus for
text/semantic/hybrid with off/rerank/filter:300 queries per cell, limit 50,
graph0, source-only, one repetition and a frozen threshold. Reports stay private.

The current-base implementation `58cbb82301dcbd6814cac22db2e4abb646f3acc8`
passes [full/native acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42380719326):
2992 Python/PostgreSQL/packaging, 40 document-browser, 27 website-browser and 28
website unit cases. Independent downloaded grading passes Debian 21, Rocky 26 with
three expected skips, eight native browser/privacy workflows, 30 accessibility
contexts and five security scans. The optional Rocky screenshot publication
failure remains preserved. Full exact-source promotion passes; [PR93](https://github.com/Stell0/ns8-czero/pull/93)
regularly merges as `7e6379260098eb80b0818a5ddcb1d80704ef289e` with the same tree.

[Core 0.42.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.42.0)
is immutably published from that tested source after
[publisher 42385896972](https://github.com/Stell0/ns8-czero/actions/runs/42385896972).
Downloaded SHA256SUMS matches: wheel
`27be1db04b68f06f1211a49474a42a5a53e8b2423736429347f0e7d53dfd711a`,
archive `10d903961937221f1dbb33575e479e4cba104c90966e85ddb5bd505bfea051e3`.
Fresh external wheel/archive installs verify independence, packaged schema0034 and
the Decisions protocol; rebuilds with the publisher's umask reproduce both bytes.
The earlier host-umask mismatch is retained as diagnostic evidence.

App0.61 adopts the immutable released tag and frozen Git lock with
`>=0.42.0,<0.43.0` and matching patch-only updater bounds. No other dependency,
Core package byte or managed-file comparison changes. The consumer runtime probe
checks the actual released Git source, schema0034 and all 19 compilation routes.
Released-Git validation passes 140 scoring/PostgreSQL/REST/current and legacy
MCP SDK/maintenance/migration cases. Pinned Node24/Renovate bounds,28 native
controllers,schemas,21 Robot dry runs and390 documentation links pass.
Consumer `827fbde711325a2f67b08ca7fee3d9ac5e950b67` passes
[full/native acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42387325979),
independent downloaded native/privacy/scan grading and exact-source full promotion.
Actual checks pass 2992 Python/PostgreSQL/packaging cases without database skips,
40 document-browser cases and 21 Robot dry runs. Debian passes 21; Rocky passes 26
with three expected skips, all eight native browser/privacy workflows and 30
accessibility contexts. All five scan/SBOM pairs pass. [PR94](https://github.com/Stell0/ns8-czero/pull/94)
regularly merges as `39c4059374d70d1ceb1604f0b29999876bee9374` with identical
tracked bytes. Actual published and installed app-image probes verify released
Core0.42 at `58cbb823` and its immutable tag, not a local producer substitution.

The actual merged consumer main passes
[full/native 42391601033](https://github.com/Stell0/ns8-czero/actions/runs/42391601033),
independent downloaded grading, exact-source full promotion and canonical image
publication. Six fresh main/latest registry reads match every digest, source
revision and immutable sibling reference; the published main app also verifies
released Git Core0.42 at 58cbb823. The source run passes 2992 actual backend cases,
40 document-browser cases and 21 Robot dry runs. Registry verification uses fresh
reads from the local and verified deployment nodes. Frozen full/native runs were
never cancelled.

The explicitly authorized dedicated installation now runs this accepted consumer.
Supported C0-only backup and full stored-data integrity pass; all 15 backup-plan
configurations are restored. Candidate released-Core database/originals preflight
is unblocked. Update preserves all 61 existing domain-table row sets, source/Wiki
bodies and identities, credentials, settings, cursors and knowledge events; only
the intended schema revision changes. Six compilation tables remain empty. The
originals store is empty; nonempty retained-file recovery remains native evidence.

Supported manager restart changes the actual app invocation and preserves content,
settings, existing schedules and ten unrelated instances. Fifty-eight table row
sets remain identical across restart; four job/schedule tracking tables advance
for successful executions of the existing health and embedding schedules. Their
exact definitions match the frozen accepted predecessor. Existing weekly
housekeeping remains enabled; compilation maintenance is not initialized.

The original ordinary owner session, current profile/space grants and five stored
Wiki reads survive update/restart. Fresh current/legacy official SDK discovery and
the existing Codex connection verify the intended account and selected index.
Bounded root application journals contain 95/44 actual entries after update/restart,
with real health, profile, guide, native-callback and MCP positive controls; query,
credential, JWT and traceback candidates are zero, including exact current-secret
fingerprint checks. External unit definitions and all unrelated module records
are preserved; unordered NS8 flags are compared as sets. Interactive-browser and
CPU-quota waivers remain unchanged; automated native browsers pass.

Freeze installed immutable tag
`ci-827fbde711325a2f67b08ca7fee3d9ac5e950b67-42387325979-1`:

| Image | Installed digest |
| --- | --- |
| Module | `sha256:e422c9f4e544e343e90a493c7da0baf055adb92044b2e6e03959ce2db56cefbc` |
| App | `sha256:7c7615d50a35ce4ec9467ba52dedded0e5a5a55f029f0ef222250272363b02f0` |
| PostgreSQL | `sha256:8f2e046dd6f0697efe6f625e199a846c9a073dab22096ba5170c5a2d035fdf0e` |

These images are the next genuine predecessor. The previous app0.60/Core0.39
installation and its immutable tags/digests below remain retained and freshly
registry-verified. Documentation-marker images never replace installed images.
After operator key configuration, real nonempty text rerank and filter calls each
score 16 candidates through OpenAI Decisions without fallback. The full nine-way
SciFact evaluation runs as a separate private one-shot with all 300 test queries
per cell, a frozen threshold/configuration and the accepted corpus receipts and
report exclusions. No benchmark quality is claimed before all cells validate.
The original importer is not restarted; no external recurring schedule or Wiki
publication is added.

## Knowledge compilation — M6 controlled acceptance candidate

M4 is accepted in [PR95](https://github.com/Stell0/ns8-czero/pull/95), regular
merge52e84a368ec6371d3eee8f546d9b3f22f53ca1d5. Its exact-head full42392187969
and actual-main [42397304098](https://github.com/Stell0/ns8-czero/actions/runs/42397304098)
pass required full/native checks and exact-source promotion verification. Source
acceptance does not change the dedicated installation or release Core0.43.

[M5](docs/knowledge-compilation/M5.md) adds selected-space English/Italian Use
with AI prompts, shared scheduling references in generated/installed archives,
and the independent c0-compile external host. It uses current scoped API keys,
Codex or Responses reasoning, durable minimal intents, source-backed publication
and independent readback. No server model execution or schedule is installed.
Core0.45 adds one alternative selected-page weekly model reservation under the
same authorization/fences/budgets; schema0036 and all six tables remain unchanged.
App0.63 retains the immutable released Core0.44 consumer lock. Plugin1.8 retains
its five skills and registered app identity. Core publication/adoption, deployment,
policy enablement, production knowledge and schedule activation remain separate.
M5 is accepted in [PR105](https://github.com/Stell0/ns8-czero/pull/105), regular
merge2b322f24f3f84e0554ffc7bae7561ae909c4462f, after exact-head
[full42418905512](https://github.com/Stell0/ns8-czero/actions/runs/42418905512),
independent native/artifact grading and full promotion verification. The optional
screenshot-publication job failed; required browser/native suites passed. Its
separate main run42423675709 subsequently completed successfully. Core0.45
remains unpublished; no publication or deployment follows from this observation.

[M6](docs/knowledge-compilation/M6.md) adds controlled compiler-backed A/B
measurement, independent answer-audit bindings and operational rollout gates.
Existing source-only builders, frozen private labels, paired SQL snapshots and
isolated read-only model episodes remain authoritative. Actual hosted ChatGPT
scheduling and retrieval quality are not inferred from a prompt, package, mock
or interactive connection. No production changes or schedules are authorized.

[Measured M6 results](docs/knowledge-compilation/RESULTS.md) record the completed
synthetic comparison with failed quality gates, authorized local-copy maintenance
acceptance and pending external private-evaluation approval. No retrieval gain or
production rollout is accepted. Exact delivery-source full/native proof remains
required for the focused tooling PR.

## Knowledge compilation — M4 producer candidate

M3 is accepted in [PR91](https://github.com/Stell0/ns8-czero/pull/91), regular
merge `c16eb49f0cfa3fb428d96dfff42222862f809289`. Exact-head full42373737405 and
actual-main [42378485191](https://github.com/Stell0/ns8-czero/actions/runs/42378485191)
pass full/native, independent artifact grading and exact-source promotion proof;
see [M3 acceptance](docs/knowledge-compilation/M3.md#accepted-source-and-post-merge-verification).
Merged M3 services and schema0034 are included in the released Core0.42/app0.61
installation accepted above, with compilation policies still uninitialized.
The [M4 contract](docs/knowledge-compilation/M4.md) adds a bounded external
post-answer observation and source-backed durable proposal using the existing
six-table coordinator and M2/M3 compiler. Search stays read-only; most episodes,
Readers, explicit read-only tasks and disabled feedback do nothing. Current
Wiki/tasks and exact originals are checked before at most one queue write and
independent task readback. Failure cannot block the already delivered answer.

Producer Core0.43 adds only schema0035’s assessment-key index to the six existing tables. Plugin1.7 retains its five skills and registered
connection; optional feedback guidance is filtered by actual capabilities.
App0.61 retains the released Core0.42 consumer lock inherited from PR94. No Core library
publication/adoption, deployment, policy activation, production knowledge or
schedule mutation is included. This frozen M4 record predates the separately
authorized M5/M6 work above; retain this historical candidate record. Exact-source full/native
acceptance and one focused PR remain required for this producer candidate.


## Embedding backlog drain

[PR86](https://github.com/Stell0/ns8-czero/pull/86) regularly merges as
`5245dbf2417d7a89b8c8bcf9a07ac16c69025e32`. Tested source
`b05ebe46e1857d7889b30e798005f7c2957a3a76` passes exact-source
[full/native acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42264181476),
the required artifact/merge gates, downloaded independent native/scan grading,
and full promotion verification. Optional screenshot publication remains failed
evidence, separate from the passing required checks. Frozen PR85 sources/runs are
retained; no full run was cancelled.

[Core 0.39.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.39.0)
is immutably published from that tested source after
[publisher acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42273069369).
Downloaded wheel/archive checksums match. It includes the previously merged
schema0033 compilation state and bounded embedding continuations, alternating
indexing with other due work within unchanged worker limits. Pausing prevents
further continuations. Source/Wiki current counts and exact report exclusions
support source-only BEIR comparisons; ingestion rejects exclusions before writes.

App0.60 adopts the immutable tag and frozen lock with `>=0.39.0,<0.40.0`
and matching patch-only updater bounds. The committed Core tree equals the tag's
tree; no local runtime override or other dependency update is introduced.
The existing managed-file registry/comparison state remains unchanged.
New fixtures restore scheduler state and remove only their own continuations.
Fresh released-Git consumer validation passes105 focused PostgreSQL/worker/BEIR/
retrieval-protocol cases; pinned Node24/Renovate API version bounds pass.

Transport review of frozen consumer966d799 reproduced dropped source/Wiki counts:
the shared response DTO omitted Core's additive fields. The correction exposes
optional counts through REST and MCP, retaining unknown counts for older Core.
Signed nonempty HTTP and official current/legacy SDK checks cover the boundary;
frozen authority schemas explicitly validate the two additions before comparison.
The released-Git consumer passes104 catalog/Wiki/annotation cases,64 HTTP/space/
BEIR cases and11 SDK/guidance/contract checks after the correction. The HTTP
regression first fails on missing fields, then passes with the response DTO fix.
The earlier consumer/full run remains uncancelled evidence, not a deployment
candidate. The published Core tree and immutable release remain unchanged.

Consumer `a8bb2e8eb15906440835ebc94b1b300d083a0f6a` passes
[full/native acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42284156460),
the actual C0 merge gate, independent downloaded native/scan grading and full
exact-source promotion. [PR87](https://github.com/Stell0/ns8-czero/pull/87)
regularly merges as `fe9e8e8d068c81df1da775fb9c78e968ac2f0201` with the same
tracked tree. Its [merged-main full run](https://github.com/Stell0/ns8-czero/actions/runs/42293129204)
passes required checks, independent native/scan grading, exact-source full
promotion and canonical publication. Six fresh registry reads match all
main/latest digests, source revisions and immutable sibling references. Earlier consumer
966d799 passes native/artifact checks but its gate correctly rejects the advanced
PR head. Optional screenshot publishing failures and other failed/private evidence
remain preserved. No full run was cancelled.

The preceding accepted dedicated installation was app0.60.0 / released Core0.39.0 /
schema0033 at the tested consumer source. Both the published app-image probe and
the installed app's package metadata verify the Git source at `b05ebe46` and its
immutable tag. C0-only backup and full stored-data integrity checks pass, with all
backup plans restored. Released-Core read-only retention preflight is unblocked.
Supported update preserves every row hash in the 54 existing tables; the six new
compilation tables are empty. No compilation workflow is initialized or scheduled.

Current source generations, original-store state, settings, schedules, profiles,
credentials and ten unrelated instances are preserved. The live originals store
is empty; nonempty retained-file recovery remains disposable native evidence.
Supported manager restart changes its invocation and preserves all 60 table hashes.
Fresh official MCP discovery and the existing Codex connection return the new
source/Wiki counts for the intended account. Real semantic retrieval has no
fallback; HTTPS health, profile, guide and text reads pass. Bounded positive-control
root journald audits after update/restart find zero credential/query candidates;
four actual credential fingerprints match. Interactive browser and CPU-quota
waivers remain unchanged; automated native browsers pass.

Installed immutable tag:
`ci-a8bb2e8eb15906440835ebc94b1b300d083a0f6a-42284156460-1`.

| Image | Installed digest |
| --- | --- |
| Module | `sha256:709faff9f7ba8bf8a4c8af1f0b88fe9dc6a86e312c5644d4518ea9c30b9a004e` |
| App | `sha256:f2386824b38ad1b8a84f1fc46db5f685f6bfdd5c9e554652327168981a274356` |
| PostgreSQL | `sha256:a4128fa5ede2e33cb4077e240f79c833663f28bcf33a10e1773b0744dfe24903` |

Freeze these identities as the next genuine upgrade predecessor. Retain the prior
app0.59/Core0.38/schema0032 installation at `c011a0b` and its immutable identities
in the [website acceptance](#vue-website--dedicated-installation-accepted).
Documentation commits never replace the installed images.

The existing ten-minute embedding schedule remains enabled. The initial backfill
uses bounded continuations and a one-off native worker drain; no recurring schedule
is added. The initial drain completes successfully with zero missing current
source/Wiki embeddings across all authorized spaces; public status readback agrees
with independent per-chunk coverage. The files-only SciFact rerun starts only
after that zero-coverage checkpoint and completes successfully. Both complete
5,183-document corpus checks pass, along with the unchanged profile/index checks.
All 300 eligible test queries run in each of text, semantic and hybrid modes;
all 900 responses use the requested mode with zero errors or fallbacks. The
comparison is valid and global source/Wiki coverage remains complete afterward.
The Markdown report, JSON summary, query log, full rankings and runtime provenance
are saved privately on the instance and locally with matching SHA-256 checksums.
Aggregate results, settings and limits are published in the
[SciFact measurements](docs/retrieval-benchmark.md#measured-scifact-results).
Private raw benchmark artifacts and operational evidence stay outside Git. No new
Wiki report is created and no stable NS8 module release is claimed.


## Local BEIR retrieval benchmark — implementation candidate

Current successor is based on original main
`6279846c27efe2a1fd0c2c7fa25d9ed7b3773ead`, preserving PR79 OAuth presentation
and PR80 knowledge-compilation M0 contracts/tests. All milestone sections remain
separate. Previous-base PR81 source `be912ff98da16a1d17d428bc9f416a1ad3fef3f9`
and its uncancelled full run42201822129 remain frozen evidence; they do not
substitute for acceptance on this new base.
Frozen PR78 source `cd7c99fe81b1d860e1c6f67741ed3e145b8d8adb` and full acceptance
[42193208055](https://github.com/Stell0/ns8-czero/actions/runs/42193208055) remain
previous-base evidence; its required native/artifact/merge gates and source proof
pass, while optional screenshot publishing retains its HTTP403 failure. Those
results do not establish acceptance on this new base. The benchmark package and
feature tests are byte-identical; runtime files, dependency locks, migrations and
managed-file state are unchanged from current main. New exact-source automatic
full/native acceptance and merge gates remain required.

Scope: repository-only CLI in `benchmarks/retrieval`, with editable local install
and separate `benchmark ingest` / strictly read-only `benchmark evaluate`.
Public MCP/API-key authentication, deterministic submissions, whole-source
readback, atomic state and ranking normalization reuse the ingestion samples.
No Core, transport, schema, runtime dependency, provider configuration or
production packaging changes are part of this candidate.

Queued-ingestion correction: the original runner waited for each extraction before
submitting the next original. The updated runner submits the complete missing
corpus first, saves each acknowledgement separately from the one uncertain write
intent, then verifies extracted bodies/chunks. Existing manifests resume without
rewriting completed sources. Evaluation still requires complete verified receipts;
acknowledged queue entries do not count as evidence. Commands and provider/runtime
configuration remain unchanged. Regression acceptance covers submission-before-read
ordering, queued resume, lost replies, missing/replaced/failed submissions, legacy
manifest compatibility and the existing corpus/authorization/evaluation guards.
The unchanged original-main baseline passes 206 ingestion unit cases; this
correction passes 255 ingestion unit cases plus five `pytrec_eval` reference
comparisons (260 total). Live submission/extraction/evaluation remain separately
reported operator evidence; these checks do not establish completed live ingestion.

The accepted local contracts require explicit account/protected-space binding,
validated standard BEIR files and graded qrels, deterministic dataset fingerprints,
a durable pending-write journal and exact source/version/chunk receipts. Complete
corpus readback precedes/follows evaluation; source inventory/revisions are checked
between modes. Space/profile embedding counts must match verified current chunks
for semantic/hybrid availability. Effective-method mismatches/fallbacks invalidate
the entire requested mode. Repeated requests measure latency without changing
quality denominators. Every run retains unique local reports and diagnostic rows.

One source per corpus item uses the existing 128 KiB text API. Oversized combined
title/body items fail whole-corpus preflight; no item is truncated, omitted or split.
Public index counts infer coverage, not connectivity or per-chunk embedding proof;
actual searches must report the requested method. See [usage and limitations](benchmarks/retrieval/README.md).

Acceptance uses synthetic datasets and the shared C0 client over a fake transport,
reference metric parity and production COPY/package exclusion checks. Live SciFact
ingestion, full instance benchmarks, deployment and provider changes are expressly
left to the operator after review. Existing documentation/agentic benchmarks and
installed runtime evidence remain unchanged.

Local executed evidence: verified original main `df1108aa1b4774cfbc124164ec86a8d0d6b38124`
passes all 206 existing ingestion unit cases. The candidate passes 248 ingestion
unit cases plus five independently executed `pytrec_eval` reference parity cases
(253 total), including three actual production package/COPY exclusion checks.
Maintained documentation passes 376 local links. A public SciFact download into
`/tmp` validates 5,183 documents, 1,109 query records and 300 test queries; maximum
combined body is 10,128 UTF-8 bytes and longest test query is 204 characters.
A second cache lookup performs no download. No C0 instance is contacted.
Normal risk classification and selected upstream CI remain separate PR gates;
these local results do not claim native/release/deployment acceptance.

## Knowledge compilation — M0 accepted baseline

The [knowledge-compilation plan](docs/knowledge-compilation/PLAN.md) defines a
SQL-backed external-agent compiler for any authorized space, disabled by default.
M0 in PR80 freezes the contracts, synthetic baseline and acceptance checklist.
M1 in PR83 adds coordination; its released Core adoption precedes the M2 candidate
below. M3–M6 remain unstarted. See the [historical baseline evidence](docs/knowledge-compilation/BASELINE.md).

## Knowledge compilation — M2 implementation candidate

[M2](docs/knowledge-compilation/M2.md) builds on accepted M1 with guarded atomic
source-backed plans, independent readback and a portable external compiler skill.
Core producer 0.40/schema0033 reuses the six coordination tables and existing
Wiki/graph/annotation services. The released Core consumer lock and deployed
runtime remain separate. Policy stays disabled by default; no discovery sweep,
retrieval hook, provider, scheduler, live mutation, publication or deployment.
Exact candidate test/CI/native evidence is recorded in the M2 acceptance entry.

## OAuth connection usability — implementation candidate

Based on original main `df1108aa1b4774cfbc124164ec86a8d0d6b38124`.
This application-only change keeps released Core0.38/schema0032, OAuth endpoints,
metadata verification, role checks, selected scopes and background consent intact.
Sign-in/consent use a focused responsive layout. Application metadata loads when
an administrator opens a pending connection or existing technical-client review;
Details is optional. An administrator explicitly approves and continues in one
step before personal consent. Technical approval confirms its result and explains
that the assistant must reconnect. Unchanged reviews skip the reapproval write,
preserving existing grant authority and client revisions.

Acceptance covers base/candidate frontend checks, PostgreSQL onboarding/consent,
real HTTPS browser code exchange and unchanged-review token survival, metadata
callback/scope boundaries, denied saves, ordinary-user approval waiting, late
drafts, light/dark desktop/phone layout and keyboard navigation. Seven added
browser regressions fail on the original UI before implementation; the ordinary
user negative control already passes. Full automatic Debian/Rocky native and
current-source C0 merge gates remain required. Base checks pass 28 unit cases,
17 controlled browsers, 30 PostgreSQL cases and two real OAuth browser cases.
Candidate checks pass 28 unit cases and 27 controlled browsers; all thirteen
real website/theme cases pass across the full run and focused recheck. The full
run retains one disposable fixture setup/teardown failure before UI execution;
its focused recheck and the real new OAuth/token-preservation case both pass.
Lint, formatting, types, production build and 372 documentation links pass.
No deployment or Grok-provider
end-to-end acceptance is claimed; the installed baseline below stays frozen.

## Vue website — dedicated installation accepted

The operator authorized the supported C0-only update on 5 November 2026.
The installed baseline is now app **0.59.0**, released Core **0.38.0**, schema
**0032**, exact source `c011a0b9b9eb57b9a0f545f21e129e8732eb65e4` from
[accepted main full/native/publication](https://github.com/Stell0/ns8-czero/actions/runs/42106339803).
Fresh exact-source full promotion verification passes before installation.
No stable module release is claimed.

The existing dedicated backup completes and passes a full Restic read-data
integrity check; its temporary plan changes are restored. All three cached and
installed image digests/source labels match the accepted CI identities below.
The supported module update and dedicated user service-manager restart pass
readiness at app0.59/Core0.38/schema0032.

Preservation verifies 50 unchanged tables/76,314 identical rows, original-file
inventory, configuration, authentication/retrieval settings, knowledge events and
space cursors, plus ten unrelated instances. Expected changes are the schema
marker, additive empty API-key table and transient login/credential-use records;
legacy OAuth grant/token counts remain unchanged. Real HTTPS sign-in and all
eight main routes pass, followed by an existing protected-space Wiki article
readback on desktop/phone and the same browser session after manager restart.
The existing connected assistant reads its authenticated profile before and after
restart. No content import, new schedule or permission expansion is performed.

Bounded root journald contains 231 entries with actual health/account/MCP positive
controls, zero OAuth/query/JWT/credential candidates, absent search canaries and
known browser credentials, and no tracebacks. Private raw evidence, failed helper
attempts and the pre-update backup remain outside Git. Both operator waivers
remain unchanged.

Freeze this installed tag and all three digests as the next genuine upgrade
predecessor; later documentation images never replace them. The former installed
`5e89055de12f46b2e87325d8fee1e6ee59dfa15d` trio remains the historical genuine
predecessor used for this upgrade.

Frozen installed tag: `ci-c011a0b9b9eb57b9a0f545f21e129e8732eb65e4-42106339803-1`.

| Image | Installed immutable digest |
| --- | --- |
| `czero` | `sha256:1f53ce284c85b6b8fe2738095c1a0e8d9a48e239f6b0891c4eca3602e169ffcc` |
| `czero-app` | `sha256:fd46e0e53f427d90737463e32e6dbcd7243d572f4b6b5858a8d95650c9718d9c` |
| `czero-postgres` | `sha256:827a93a604708e15c79101e1e015817e0d832523955f70ec3ead42bb8743adaf` |

## Vue 3 website remake — source and publication accepted

[PR75](https://github.com/Stell0/ns8-czero/pull/75) replaces the reference
website with Vue 3, TypeScript and Nebula: English/Italian, light/dark/system,
phone/desktop layouts, persistent space selection and search. App 0.59.0 keeps
released Core 0.38.0 from `2eb0b453f329f2f1044ff6151854298aac1b7e88`
and schema 0032 unchanged. Native NS8 settings remain Vue 2/Carbon.

Home, Wiki, Sources, Projects and Explore are read-only knowledge views.
Source upload/replacement/reprocessing/recovery, Account/API keys, connections
and administration retain their existing authority. Original retention is opt-in;
download links require retained, accessible versions. Replacements preserve the
published document until whole-document validation. Authentication presentation
uses the existing server-gated cookie/CSRF/consent flows. Assets and fonts are
local; legacy website controllers are removed. See
[contracts and coverage mapping](docs/vue-website.md).

Original baseline `b317619322ab0a59af038186db8e55e749f94ff6` passes 2,775
backend/database/packaging cases with English/Italian OCR. Exact reviewed source
`172b31901076dbf2082c98544cb250a8b3ddbb99` passes
[full/native 42096335384](https://github.com/Stell0/ns8-czero/actions/runs/42096335384),
including 2,799 backend/database/packaging cases, 39 real HTTPS browser cases,
28 Vitest cases, 17 controlled browser cases, 27 Node tests, lint/format/types/build,
schema/shell checks and 21 Robot dry runs. English/Italian have 260 matching keys.
Targeted negative controls and eight failed-source language/theme/layout/keyboard
contexts also pass after the corresponding corrections.

Independent downloaded-artifact grading verifies Debian upgrade 21 passed and
Rocky installation 26 passed/three expected skips, all eight browser workflows,
30 numeric accessibility contexts, ten access phases, eight privacy guards,
three OAuth-query artifacts with zero candidates and five scan/report pairs.
All three role workflows prove saved API-key revocation with HTTP 401 readback.
Native evidence also covers provider sign-in/consent, remembered and background
authority, renewal/revocation, source recovery and backup/update/restore.
The actual immutable app image independently passes runtime/license inventory,
released-Core Git/schema, compiled asset/font/CSP/route and source-label probes.
The current-base/diff/full promotion verifier and actual C0 merge gate pass.

PR75 regularly merges as `c011a0b9b9eb57b9a0f545f21e129e8732eb65e4`.
Actual merged-main [full/native 42106339803](https://github.com/Stell0/ns8-czero/actions/runs/42106339803)
passes the same complete local/native checks, independent artifact and actual
image audits, full promotion verification and canonical publication. Six fresh
registry reads at 21:48 UTC on 5 November 2026 verify each `main` and `latest`
alias against the accepted digests
and exact source labels. These identities remain frozen when documentation main
advances.

### Reviewed candidate images

Frozen tag: `ci-172b31901076dbf2082c98544cb250a8b3ddbb99-42096335384-1`.

| Image | Immutable digest |
| --- | --- |
| `czero` | `sha256:de85ba5258bd828b58495948a2f1a53a3ff84a57287328a31adb6820959299f2` |
| `czero-app` | `sha256:2dfadb38c1f494d9a5d9ad5fb98268ad2fc2cf9d3ff5bcea5a1328c5472b7cda` |
| `czero-postgres` | `sha256:0c1c1b4eee164ac3661c239c52c9f375f6bd5a863c08b5fd2d711f289fd37a39` |

### Accepted merged-main images

Frozen tag: `ci-c011a0b9b9eb57b9a0f545f21e129e8732eb65e4-42106339803-1`.

| Image | Immutable digest |
| --- | --- |
| `czero` | `sha256:1f53ce284c85b6b8fe2738095c1a0e8d9a48e239f6b0891c4eca3602e169ffcc` |
| `czero-app` | `sha256:fd46e0e53f427d90737463e32e6dbcd7243d572f4b6b5858a8d95650c9718d9c` |
| `czero-postgres` | `sha256:827a93a604708e15c79101e1e015817e0d832523955f70ec3ead42bb8743adaf` |

Earlier failed runs remain preserved: explicit font MIME packaging, obsolete
native selectors, initial filter URL/focus/pagination, dialog completion and
search-details remounts, saved key revocation and failed-source retention/Reader
boundaries were corrected and exercised. The preceding `0309338` passes full
local/native/artifact checks but its gate correctly rejects the superseded PR
head. The original final-source run `42081177164` is retained; the fresh complete
run above provides the selected proof. Separate targeted passes never substitute
for an unsuccessful candidate's full acceptance. No frozen run was cancelled.

At this source/publication checkpoint, the installed app0.57/Core0.37/schema0030
baseline at `5e89055de12f46b2e87325d8fee1e6ee59dfa15d` was unchanged. No live
update, stable module tag, Core release, import or external schedule is included.
Both operator waivers and all private/failed evidence remain preserved.

## Personal API keys — released consumer accepted

App0.58.0 adopts independently published Core0.38.0 and schema0032. Personal
REST/MCP keys use hashed credentials, explicit scope/space ceilings, optional
expiry, browser-only lifecycle and ingestion-client support. Permission changes
invalidate keys, including older-writer edit/regrant through revision snapshots.
The original verifier fails the new negative control; corrected migration,
authorization, SDK writes/readback and legacy-token compatibility checks pass.

[PR72](https://github.com/Stell0/ns8-czero/pull/72) publishes the reusable service;
[PR73](https://github.com/Stell0/ns8-czero/pull/73) regularly merges the released
consumer as `1a92b7aebbec3c5ad217f03e84f2b57a250f9d18`. Exact consumer source
`00ffd370c0f9c9241eed26c91d7725078cea86e7` passes
[full/native41840958720](https://github.com/Stell0/ns8-czero/actions/runs/41840958720):
2,775 Python/database/packaging cases, 24 real browser workflows, 219 Node cases,
schema/shell checks and 21 Robot dry runs. Independently downloaded native reports,
scan reports and exact-source full promotion pass. Actual merged-main
[41851447750](https://github.com/Stell0/ns8-czero/actions/runs/41851447750) passes
full/native acceptance and canonical publication, with independent artifact
grading and six fresh registry identity reads. The original promotion verifier's
optional-screenshot failure is preserved below; PR75 corrects its actual-suite
selection and verifies this historical main with the full command.

See [API key contracts](docs/api-keys.md) and the evidence below. The installed
app0.57/Core0.37/schema0030 baseline stays unchanged. No live update or stable
NS8 module release occurs; both operator waivers and failed/private evidence remain.

> **Document ingestion modernization (M0–M10 implementation merged; model quality open):** [queued extraction units, selective retries, structured documents, optional OCR and selective context retrieval](docs/ingestion-pipeline/PLAN.md). Execute one independently tested milestone at a time; the separately authorized dedicated deployment is recorded below.

## Queued document extraction — implementation merged

The [approved extraction plan](docs/ingestion-pipeline/PLAN.md) proceeds one
milestone per reviewed PR. M0–M10 implementations are merged; M10 model-quality
acceptance remains open. The
[contracts](docs/ingestion-pipeline/CONTRACTS.md) specify canonical assembly,
bounded manifests/results, PostgreSQL leases, authorization, publication and
cleanup. [Baseline evidence](docs/ingestion-pipeline/BASELINE.md) records synthetic
originals, current whole-document retry/locking behavior, citations and external
multipart readback. M0 changes no runtime, schema, dependency or connector contract.
M0's contract review authorizes the separate [M1 implementation](docs/ingestion-pipeline/M1.md).
M1 full `41605913790` passes and merges as `6380d38`. The
[M2 producer candidate](docs/ingestion-pipeline/M2.md), Core 0.37.0/schema 0025,
adds PDF page units, failed-unit retry and complete atomic publication. The
operator authorizes isolated successor development while prerequisite CI runs,
with sequential acceptance/merges and disposable instances for native/rollout
tests. Ordinary extraction and the released consumer lock remain unchanged.
M2 exact `cfecd8c` passes 2,619 local Python/PostgreSQL/packaging cases without
skips, including independent predecessor/wheel/source proofs. Failed environment
and probe evidence is retained. PR58 regularly merges as `d2fc9a5` after full
`41616861662` and `41620456266`, including native/artifact gates and exact-source
promotion verification.
The [M3 successor](docs/ingestion-pipeline/M3.md), schema 0026, adds configurable
native workers, fair leases, queue/result backpressure and actual resource/restore
grading. Focused pool/package checks pass 74 cases and Robot dry-run passes all
21 cases; complete local Python/PostgreSQL/packaging passes 2,661 cases.
PR59 regularly merged as `ed160592cd42f711a78dc8f861497ccc42c859cd` after full
`41654247380`, both native distributions, independent artifact audit and exact-source
promotion verification. The earlier native retrieval failure remains preserved;
fixtures now seed before indexing is paused and snapshotted. The [M4 implementation](docs/ingestion-pipeline/M4.md)
adds canonical DOCX block and Markdown/text range extraction. Its exact current
local suite passes 2,677 cases; full/native 41666816436, independent artifact grading
and full promotion verification pass. Ready-transition full/native `41668554721`
also passes; PR60 regularly merges as `b51112e15693f456384b231a675ce651949d3efd`. The [M5 successor](docs/ingestion-pipeline/M5.md) adds bounded
current structure and versioned section chunks. Original final source `2afbe4a`
passes 2,682 complete local cases; the code-identical accepted-base candidate
passes 15 focused structure/migration/source HTTP cases. M5 native gates remain. M10 measurements exposed a valid large Markdown body
rejected by optional structure bounds; the successor preserves complete body
publication with explicitly recorded fixed chunks when only derivatives overflow.
No model answer-quality improvement is claimed.
The [M6 successor](docs/ingestion-pipeline/M6.md) adds opt-in local page OCR,
backend/model fingerprints and synthetic scan/timeout/disable checks. Native
fixtures now verify an OCR page alongside ordinary pages before/after restore.
M5 repaired source `b2c87b5` passes full/native `41687775493`, independent
artifact grading and promotion verification, then regularly merges as `b0db3d2`.
The original PR61 remains frozen and superseded. M6 retains the repair and passes
2,700 full local cases plus 32 focused controls before its own native acceptance.

The [M7 cache successor](docs/ingestion-pipeline/M7.md) adds current-owned
reuse without another body store. The cache/queue/formats/OCR/configuration/backup
selection passes 110 cases, including expiry, revocation, protected-space and
A→B→A checks. Acceptance remains sequential.
M6 exact `064a7bf` passes full/native `41699410483`, independent artifact grading
and promotion proof, then regularly merges as `39dc9cc`. Both distributions prove
actual OCR with two/four workers and restored readback. M7 retains complete-body
bounds and conservative same-space current/staging ownership.
M7 exact `0b3732f` passes full/native `41708740692`, independent artifact grading
and full promotion verification, then regularly merges as `e9a485f`. Its local
CI passes 2,710 Python/database/package cases, 15 browser workflows, 211 controller
checks and 21 Robot dry runs. Both native distributions and actual OCR/resource/
restore evidence pass. M8 remains the next sequential acceptance gate.
The [M8 context candidate](docs/ingestion-pipeline/M8.md) adds four read-only
operations, exact generation guards, bounded selected evidence and plugin 1.4
research guidance. Current/legacy SDK, native guided-probe, multipart, OCR
provenance and generated-package checks pass 65 focused cases.
M8 original `4589600` passes 2,732 Python/database/package cases and Debian but
fails one Rocky OAuth-browser assertion against the new guidance inventory.
The isolated successor preserves exact old/new catalog counts, adds stable
workflow IDs and exposes read-only context guidance to authorized Readers.
Four actual role/space browser controls and 213 local controller cases pass;
current-source full/native acceptance remains required. Failed evidence stays.
M8 repaired exact `0d522b0` passes full/native `41727509130`, independent
artifact grading and full promotion verification, then regularly merges as
`dd5f341`. All 2,732 Python/database/package cases, 19 browser workflows,
213 Node 24 controllers, 21 Robot dry runs and both native distributions pass.
The failed PR65/source remains closed and frozen. M9 uses accepted repaired main.
The [M9 progress/recovery candidate](docs/ingestion-pipeline/M9.md), schema 0030,
adds reader progress, Admin diagnostics, retry/cancel and retained-original
reindex. Current 28 focused controls pass; its code-identical integration source
passes all 21 browser workflows. Core publication and released-consumer adoption
remain separate M10 gates.
Installed baselines, frozen evidence, Core publication,
consumer adoption and separately authorized deployment gates remain.

M9 [PR67](https://github.com/Stell0/ns8-czero/pull/67) regularly merges as
`ec7f45c8859357b486a21042484b7a338b8978d6`. Exact `37ce3cec` passes full/native
[41737196843](https://github.com/Stell0/ns8-czero/actions/runs/41737196843),
independent artifact grading and full promotion checks: 2,741 Python cases with
no skips, 21 browser workflows, 219 Node 24 controls, 21 Robot dry runs, Debian
21 and Rocky 26/three expected skips. All native browser/privacy, OCR/resource/
restore and five image scans pass. Earlier pending statements describe retained
checkpoints; M10 consumer/native/model-quality gates remain separate.

M9 actual main `ec7f45c` passes full/native/canonical publication
[41745904240](https://github.com/Stell0/ns8-czero/actions/runs/41745904240), with
independent artifact and exact-source full promotion proof. Core
[0.37.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.37.0) is immutably
published from accepted `37ce3cec` by
[41754099289](https://github.com/Stell0/ns8-czero/actions/runs/41754099289): eight
independent package cases pass and downloaded public assets match prepared bytes.
Publisher repair PR68 regularly merges as `2096f11` after its own full/native/
artifact acceptance; the original failed run and signed tag remain preserved.
M10 adopts the frozen tag/lock and schema 0030 on that accepted main, retaining
all Core package bytes. Final consumer/native/main gates remain; model quality
is explicitly open and the live baseline/default remain unchanged.

M10 [PR69](https://github.com/Stell0/ns8-czero/pull/69) regularly merges as
`84a0bcd09de6e2f5b4d263c7509c977488505415`. Exact `b22d7c9` passes
[full/native 41754721407](https://github.com/Stell0/ns8-czero/actions/runs/41754721407);
actual merged main passes
[41761803984](https://github.com/Stell0/ns8-czero/actions/runs/41761803984), independent
artifact audits and exact-source full promotion. Both current CI and the separate
Git consumer pass 2,760 Python/database/package cases without skips, including
the actual published Core distributions. All 21 browsers, 219 Node 24 controls,
21 Robot dry runs, five scans, Debian 21 and Rocky 26/three expected skips pass.
Actual published/native released-Core identity, OCR/resource/restore, no backfill
and two/four-worker reindex pass. Canonical publication and six fresh registry
checks match [the immutable images](docs/ingestion-pipeline/M10.md#accepted-main-publication).
Model/held-out answer quality stays open by operator decision; no model calls,
default-on rollout, production import/reindex, new external schedule or stable
NS8 module release occurs. The separately authorized live upgrade is recorded
below. Earlier pending wording records retained checkpoints.

## Ingestion deployed runtime and frozen predecessor — 4 November 2026

The operator separately authorizes the dedicated C0 update. The installed source
is `5e89055de12f46b2e87325d8fee1e6ee59dfa15d`, app **0.57.0**, independently
released **Core 0.37.0** at `37ce3cec4c8de2778f90792b7abd9202d5357791`, schema
**0030_explicit_reindex**. Exact merged-main
[full/native 41774490933](https://github.com/Stell0/ns8-czero/actions/runs/41774490933),
independent downloaded native/artifact grading, canonical publication and fresh
exact-source full promotion pass. Fresh registry reads and both actual installed
image inspections verify all three immutable digests below. The installed app's
`direct_url.json` verifies the released Core Git source and tag, without a local
producer fallback. Documentation descendants do not replace this installation.

All three images retain tag
`ci-5e89055de12f46b2e87325d8fee1e6ee59dfa15d-41774490933-1` in `ghcr.io/stell0`:

| Image | Installed digest |
| --- | --- |
| `czero` | `sha256:4e406cf1a6765aac0138551313114151915605f775276b5dd01767dc0e6ad8fb` |
| `czero-app` | `sha256:5469c1d718f28bdf5f0b4f0edd213e04815379a6457df04453bc97c6cc7014f8` |
| `czero-postgres` | `sha256:f1a85e8f62c51676bb842773581f5af190b82b396006bc87f624dd1520a0c68d` |

The genuine immediately preceding installation is app 0.57.0 / Core 0.36.1 /
schema 0023, source `96b55d81dfd91be3dc0190796755a50ae9d983b9`, tag
`ci-96b55d81dfd91be3dc0190796755a50ae9d983b9-41487239536-1`. Preserve its
`czero` digest `sha256:5a339ec16308b49ab98a0f8d3fc965ef400f804747d14222e41eb738ad6f6160`,
`czero-app` digest `sha256:955cb026e6299a565dc61252f405a8cee1a0ded06b154e196902fbd7fb519fd1`
and `czero-postgres` digest `sha256:68c63729eaf6f2c348a4f1931021d719f50b7c678332881c9468a31003e56d3f`.
Earlier `31b0c85` and other installed checkpoints remain historical evidence.
Use the newly installed three-image identities as the next genuine predecessor.

Supported C0-only backup and full repository read-data integrity pass. All fifteen
backup plans return to their original configuration, with the owned one-off plan
disabled and empty. New-Core read-only retention preflight passes before and
after the upgrade. No retained original files are present, so this live instance
does not establish nonempty original-file retention; native clean-restore and
original/reindex acceptance remain the separate full-CI evidence.

The supported targeted `update-module` completes successfully in 28 seconds;
the supported dedicated module-manager restart also passes. Trusted HTTPS
readiness, configuration, runtime, both containers, ordinary worker timer and
extraction timer pass after both operations. There are no matching update/restart
rows in the local API audit database; action receipts plus actual installed state
establish the operations, without manufacturing an HTTP audit entry.

Independent old-column projections preserve **74,362 stable rows across 44
original domain tables**, including **1,207 source documents, 9,430 chunks and
13 Wiki pages**. Existing content counters/events, four exact protected Wiki
reads, settings, mounts, authentication/retrieval configuration, routes, domains,
all six original persistent grants and ten unrelated module identities remain
unchanged. The existing external ingestion timer retains its schedule; its job
is not run as an acceptance fixture. The existing browser session survives both
operations, fresh ordinary native sign-in works, and actual connected MCP
profile/space reads preserve account identity and grants before/after both.

The runtime advertises **122 operations**, including all four new read-only
context operations. Real selected-space outline, section and context-bundle
reads return exact original spans with citations and no whole-document fallback.
The public skill archive is valid; actual plugin **1.4.0** download exactly equals
the offline package for the existing registered connection identity. Public local
font/CSS bytes match accepted source after update and restart. This client's
cached plugin is still 1.2.0 and its catalog lacks the four new operations; a host
catalog/plugin refresh remains pending. Existing connected reads pass; no new
consent, connection replacement or broadened scope is performed.

Extraction and OCR remain **disabled**; two-worker resource defaults are added by
the supported lifecycle. There are zero extraction runs/units, persisted structure
backfills or forced reindexes after update and restart. Both bounded root app
journals pass, with **36 and 38 actual entries**, successful health/profile/guide/
native-callback/MCP positive controls and zero query, credential, JWT or traceback
candidates. Empty Podman logs are not used as privacy evidence. Private backups,
credentials, raw observations and failed observer assumptions stay outside Git.

This accepts the separately authorized live upgrade, not a default-on rollout,
model-quality comparison, production reindex/import, new schedule or stable NS8
module release. Model/held-out answer quality remains open by operator choice;
no model calls occur. Interactive Playwright and CPU-quota waivers remain intact.

## CI policy update — implementation

The operator prioritizes test speed over realistic fixtures in fast feedback:
unit/controller/template/syntax checks run without PostgreSQL, browsers or
extraction workers; real database/browser/packaging checks stay in full
acceptance. The operator authorizes fast checks on every PR, automatic Debian/Rocky native
acceptance for installation/container/migration/authentication/dependency and
other uncertain changes, and native tests on demand for reviewed presentation
changes. Merge eligibility and full release/deployment acceptance are separate
proof levels. Human review is optional in C0; reviewed agent changes may use
GitHub automatic regular merges after current-source required checks pass.
Keep strict branch protection, exact source/base/diff binding, immutable images
and all full-native release/deployment gates. Preserve the Nebula branch and
its full main acceptance run41464774914 without cancellation. That preserved
run has now completed successfully; the new verifier accepts its frozen full
proof for source8d12015e30d33d482a07bff66f641aa77a3f1f9a.

A first local fast-path run passes in 74.23 seconds without database/browser/
worker fixtures. Focused policy/release regressions pass 161 cases. These are
executed development results, not full native release/deployment acceptance.

Implementation and acceptance cover classification, fast/full workflow jobs,
versioned proofs with frozen-proof compatibility, promotion rejection of fast
proofs for release/deployment, project-aware nethserver-pr guidance, and native
GitHub auto-merge without an admin bypass or new privileged PR event. Test mixed
diffs, renamed/deleted files, auth/dependency boundaries, stale heads/bases,
failed/skipped required jobs, manual/tag full requests and old full proofs.


## Nebula website redesign — implementation candidate

The reference knowledge website in `app/static` adopts Nebula foundations while
retaining its plain HTML/JavaScript stack. NS8 settings remain Vue 2/Carbon, as
required by the frontend skill. Scope includes shared navigation, local Poppins
Regular/Medium, semantic light/dark colors, reading layouts, forms, tables,
notifications, keyboard focus and responsive spacing. Existing DOM IDs, source
and Wiki rendering, space selectors, request/draft guards, permissions and
OAuth behavior remain the acceptance contract. No Core, schema, connector or
production deployment change is planned.

Acceptance: verify the exact original-main baseline; run application/template
and controller regressions; exercise actual disposable HTTPS/database/worker
browser workflows; inspect light/dark desktop/phone layouts and keyboard focus.
Run Nebula mechanical checks adapted to HTML/CSS. Full exact-source CI and native
acceptance remain mandatory before promotion. Keep local fonts and their license
in the shipped static inventory; no external browser asset requests are allowed.


The exact original-main baseline `4643cfb` has full CI41428851518 acceptance;
`verify-promotion.py --full` rechecks its completed required jobs and proof.
Local released-Core validation uses the frozen app lock and immutable Core0.36.1
source `8dbb746`. Current candidate evidence: 211 Node24 controller cases,
15 actual HTTPS/PostgreSQL/worker browser workflows, all 40 new light/dark
phone/desktop page contexts with accessible-name/landmark checks, 21 Robot dry
runs, Go schema, shell and documentation checks. Nebula mechanical checks find
no unsupported weights, template colors, inline styles or nonsemantic click
handlers in the changed templates. The two local font files match the verified
public npm archive and retain its OFL license; they receive explicit binary
review rather than a privacy-check exception. Full local Python/database/
packaging validation passes 2,461 cases with no skips (1,329.92 seconds); the
final theme/menu check passes after the typography and contrast adjustments.
Final exact-source image/native/privacy/scan CI remains required before merge.


## Released-Core adoption candidate

PR48 regularly merges as `53c6957`; its tree equals accepted head `8dbb746`.
Exact PR full CI41110893198, promotion proof and downloaded native/privacy
artifacts pass. Main run41192441500's required Rocky job fails during the upstream
NS8 installer's package-mirror metadata download, before that guest's C0 suite.
After the public mirror recovered, all nine metadata objects passed full download,
size and checksum verification. Fresh full main41235861770 and adoption control
e8a88d6/41235873073 pass, including actual main canonical publication and promotion
proofs. Independent downloaded artifacts verify Debian21, Rocky26/three expected
scenario skips, eight native browser workflows/privacy guards, 32 accessibility
contexts and five scan/SBOM pairs. Both actual local jobs pass2411 Python/database/
packaging and13 real browser cases. The original failed evidence is preserved.

Independent Core0.36.1 is published from the merged, fully accepted `8dbb746`
source by [41193447358](https://github.com/Stell0/ns8-czero/actions/runs/41193447358).
Downloaded wheel SHA-256
`78cf510a4fe4752e0761de037f3f4b8be14383a94d223b9cbe389535ad28ef5f`
and archive `4a4b221c452094d5f4d7ac92f4f51cc1a0eba0b8038020a45041993570e253e0`
match its immutable release checksums. Source, license, Authlib1.9.1 and schema0023
are verified; this independent library publication is distinct from app
acceptance and does not constitute an NS8 module release.

App0.57 stages adoption of the released tag, frozen Git lock and matching
patch-only updater bounds. No retrieval algorithm or stored content changes.
The accepted control still publishes local Core because reference publishing
unconditionally selects producer mode; its released-source probe is a separate
temporary image. Actual logs confirm that mismatch even though committed Core
content equals the locked release. The successor compares those Git package trees
and verifies released provenance in the actual image to be published and tested
natively. Different upstream Core trees retain producer CI; forks stay released,
and invalid identity never causes fallback. Core bytes/schema/ranking are unchanged.
Complete successor consumer/native/current-PR gates and review remain required
before merge and guarded live acceptance. Do not deploy producer/local Core as
a substitute for a released consumer dependency; preserve failed/frozen evidence.

## Agentic retrieval workflow (development)

Maintenance recovery follow-up: multiple quotes from one current chunk retain
their distinct page bindings and use one verification reference. The regression
uses Core's actual annotation normalization and checks that a repeated unchanged
run performs no writes. Authored verification conflicts remain protected. No Core,
runtime, migration, policy, schedule or compiler milestone change is included.

Build three source-grounded skills and a bounded external comparison runner,
reusing real disposable C0 MCP and the existing isolated model driver. Freeze
question partitions, corpus hashes, model/budgets and numerical targets before
candidate measurement. Manage only reviewed source-backed Wiki navigation in the
minimal semantic profile; initial construction sees no questions. Validation and
sealed outcomes are single-use. Production enrichment, deployment, schedules and
merges are outside this task. See [protocol and limits](docs/agentic-retrieval.md).
The preparation follow-up supports full paginated multipart selections, explicit
corpus budgets and bounded source packets. Default benchmark mode records quality
failures while measuring each held-out split once; optimization retains its
selection gates. Exploratory development does not require an audit and cannot
claim acceptance. Existing frozen measurements remain unchanged.
Actual pilot and full acceptance results must be recorded separately; preparation
or synthetic tests alone do not establish real-corpus quality.

## Bounded natural-language retrieval candidate

Controlled signed-HTTP reproduction identifies lexical eligibility before ranking:
the `simple` web-search query requires every term in one chunk. Independently read
bodies, keyword/phrase/operator controls and actual GIN access distinguish this
from missing content, authorization, providers or a benchmark fallback. Chunk
co-occurrence and absent product/version words are separately observed mechanisms.

Core 0.36.1 preserves strict matches, then uses bounded provider-free lexical
recovery for eligible zero-result plain queries. Standard stop lists, minimum
term coverage, mandatory identifiers and current product/version provenance are
shared by ordinary, filtered and source callers. No schema, dependency or global
retrieval-setting change is introduced. Optional response metadata and guidance
distinguish lexical relaxation from semantics. See [the contract](docs/retrieval-benchmark.md).

Initial question regressions fail before the correction; explicit syntax controls
pass. Scoped Core/HTTP/current-generation and hand-computable benchmark cases pass,
as does real HTTPS/OAuth renewal and question-to-complete-document browser
navigation/replacement/access loss. Full exact-source local/native/artifact gates
and a fresh held-out comparison are required before review readiness; record
their exact results in the PR. Private labels/results stay outside Git.
The independent Core publication, consumer pin/lock adoption and
consumer acceptance gates precede any deployment. No new PR is merged or release
published automatically; accepted installations and predecessors remain frozen.

## Operational documentation and retrieval tooling

Implement a small external, read-only retrieval runner using the existing
dedicated ingestion connection and complete-document APIs. Freeze current
identities/hashes before and after each mode; retain provisional analyst labels,
raw chunk rankings and parent-deduplicated metrics privately. Missing providers
and comparator access remain explicit unavailability, not simulated measurements.
An opt-in external publisher batch queues bounded extraction before the existing
verification/publication path, preserving uncertain-intent and lease contracts.
Acceptance includes hand-computable metrics, current-corpus/authority/fallback
regressions, real PostgreSQL staging/recovery and the existing HTTPS worker/browser
suite, followed by full candidate CI. Runtime/Core storage behavior is unchanged.

> Latest-only semantics replace the previous content-history guarantee. Each logical source document and Wiki article retains one current complete generation. Old exact citations and superseded mutation replays return `content_superseded` (410); stable links open current content. Back up before the destructive upgrade and run the [read-only preflight](docs/latest-only-migration.md).

## Active: latest-only storage and reusable website crawler

Authorized scope: disposable storage/migration/browser validation and bounded
public documentation reads only. The approved source merge is complete as
recorded below. Production migration, import and schedules require separate
authorization. Preserve frozen deployed images and historical evidence below.

Implementation uses schema 0023, explicit current source pointers, verified current
multipart membership, payload-free receipts/tombstones, transactional retirement
and durable original-file cleanup. The reusable website adapter uses the existing
private-job OAuth/client/publisher, approved boundaries, robots/sitemaps, resumable
frontier and pinned structured Markdown conversion. See the
[migration note](docs/latest-only-migration.md) and
[recipe/catalog](samples/ingestion/examples/website/README.md).

Baseline original main: `d98d5b498bcbf70d04015b3d8c9e2afdf3bb80c8`.
Actual baseline: 2322 Python/PostgreSQL/packaging, 207 Node, six real HTTPS browser
cases, schema/shell/docs and 21 Robot dry runs pass. Full CI
[40823668206](https://github.com/Stell0/ns8-czero/actions/runs/40823668206) and its
downloaded native/privacy/five scan-SBOM pairs pass independent artifact audit.
Frozen Core source `cf9c0fa38183e940877c13228a8ce753dfd07412` passes
2352 Python/PostgreSQL/packaging cases, 207 Node controllers, ten real HTTPS
browser cases, schema/shell/docs and 21 Robot dry runs. Full CI
[40954071273](https://github.com/Stell0/ns8-czero/actions/runs/40954071273) passes;
independently downloaded artifacts verify Debian update 21, Rocky installation
26/three expected skips, eight browser workflows/privacy guards, 32 accessibility
contexts, three OAuth-query artifacts with zero candidates and five scan/SBOM pairs.
Actual independently installed predecessor 0.35.2 content survives the destructive
upgrade with current identities intact; failed/corrupt preflights block removal.

Immutable [Core 0.36.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.36.0)
is published at that source by
[40964016296](https://github.com/Stell0/ns8-czero/actions/runs/40964016296).
Downloaded wheel SHA-256 `e765f790fa979c38b598fdcaa0bf41936ba29523fca2fa31bb9191a30cb2bda9`
and archive `24f9b04cc5fba68428693b78d0a112cd21dc1597dc996613bbceb760ee19e8ef`
match published checksums. The application adopts its immutable tag/Git lock,
`>=0.36.0,<0.37.0` and matching patch-only updater bounds. Default-image acceptance
checks the actual installed source and latest-only schema/contracts. Approved
[PR45](https://github.com/Stell0/ns8-czero/pull/45) regularly merges as
`f51357d18760a83242273e1ded0c648799c8dad8`, preserving tested head
`51b8309fc833feb1e8e3d8302e46df9f680cfb34` and its identical runtime tree.
PR full [40992071146](https://github.com/Stell0/ns8-czero/actions/runs/40992071146)
and actual main [41010999070](https://github.com/Stell0/ns8-czero/actions/runs/41010999070)
pass the merge gate and exact-source promotion verification. Main confirms
2378 Python/PostgreSQL/packaging cases, 210 Node controllers, eleven real HTTPS
browser cases, schema/shell/docs and 21 Robot dry runs. Independent downloaded
main artifacts verify Debian update 21/zero skips, Rocky installation 26/three
expected install-only skips, all eight native browser workflows/privacy guards,
32 accessibility contexts, three zero-query artifacts, genuine predecessor
content/background preservation, three installed candidate identities and five
scan/SBOM pairs. Canonical publication succeeds; six fresh registry reads verify
all three main/latest aliases against those accepted digests and source labels.
This closes source/publication acceptance. Production remains untouched; the
accepted installed baseline below is unchanged. Backup/preflight, a production
upgrade, documentation import and external schedule require separate authority.

Consumer acceptance exposed an existing source-upload race: selecting a source
could submit before its title/provenance lookup completed, accidentally making an
unchanged upload a metadata edit. The form now waits for the latest successful
lookup, preserves authored metadata when choosing a file and reports acceptance
only after refreshing current content. Three controlled regressions fail before
the fix and pass after it; the real HTTPS/worker/browser regression confirms the
unchanged upload retains source revision and content identity. The preceding
Rocky native failure remains failed evidence, not acceptance. The corrected
head passes 2378 Python/PostgreSQL/packaging cases, 210 Node controllers and eleven
HTTPS browser cases. Its full consumer and subsequent main/native acceptance
are recorded above; no failed run is counted as a pass.

Bounded public smoke uses 20 pages each from NethVoice, NethSecurity and NethServer.
After correcting article-header extraction, all 60 whole Markdown bodies and
headings pass actual C0 interface/hash readback in fresh disposable spaces; a
Reader opens one from each site. All 60 unchanged readbacks preserve generation
identity and perform zero C0 writes. Each selection is page-budget partial
coverage. Current cached HTML receives 20 conditional 304 responses per site and
is reconverted with the new extractor fingerprint. No production data or instance
is used. A transient NethSecurity DNS failure remains failed evidence; its bounded
retry passes without weakening network restrictions.

| Site | Verified pages | Requests / 304 | Crawl / conversion seconds | Publication / extraction / readback seconds |
| --- | ---: | ---: | ---: | ---: |
| nethvoice | 20 | 22 / 20 | 20.153 / 0.360 | 29.984 / 7.885 / 4.764 |
| nethsecurity | 20 | 22 / 20 | 19.997 / 0.385 | 28.601 / 8.628 / 4.827 |
| nethserver | 20 | 22 / 20 | 19.852 / 0.433 | 29.288 / 8.084 / 4.581 |

Fetched corpora stay private. The crawler keeps current representations and a
bounded resumable pending scan, then retires only its owned obsolete payloads.
Interrupted frontier progress is replayed until the batch is durably saved;
robots-denied discovery stays partial. Dedicated website private jobs may target
the same project as other adapters, but mixed-adapter private jobs are rejected.
App original-file delivery pins and hashes the authorized generation before
streaming; an in-flight retired generation remains explicitly identified while
new exact requests return authorized 410. No external timer is installed.

Initial feature CI [40945036958](https://github.com/Stell0/ns8-czero/actions/runs/40945036958)
exposed a clean-environment producer override error before tests. Its produced
images, scans and native runs are preserved diagnostic evidence. The next
candidate pins the explicit local producer path without modifying consumer pins.
The initial 2350-case local run retained six failures (2344 passes): stale replay
assertions in bundle/package probes and a synthetic source left in Shared. The
current-only probes and explicitly scoped fixture fix those causes; all eight
actual independent wheel/archive package cases and 40 sequential storage cases
pass. The native upgrade verifier now follows established disposable TLS trust
restoration; initial ordering/DNS failures remain failed evidence, not acceptance.
All full/native/final consumer gates remain required. Initial multipart imports now
have one visible body-free pending entry; the real Reader automatically opens the
complete parent after publication. The 18-case document suite, including the
10,000-parent bounded directory, and the real pending-to-current browser flow pass. The
initial Rocky browser diagnostics exposed obsolete history-count/old-body and
whole-receipt text assertions. Native checks now require current-only listings
and authorized 410 responses. Reader/read-only-token version lists exclude staging;
Editors/Admins with write scope retain bounded verification access. All exact-source
full/native gates must pass before Core publication and consumer adoption.

The completed PR44 section below records its historical guarantees. Latest-only
semantics explicitly supersede its content-history promises.


C0 has two uses: a shared second brain for people and assistants, and a reusable starting point for AI knowledge applications. See [README](README.md) for the product, architecture, data model, setup and fork walkthrough.

## Full documents in Knowledge Explorer — implementation in progress

Original-main base: `e30bb449b165cac4a0c4b8cafaf950f64ed0675c`, isolated
`feat/full-document-explorer`. Full baseline run 40723318218 passes;
local baseline passes 2303 Python/PostgreSQL/packaging, 197 Node (also pinned 24),
21 Robot dry runs and schema/shell/docs. Initial feature regressions fail before
implementation. Focused Core/ingestion now passes 24 and reader controllers 25.
The parent-aware unchanged-part history regression failed before its writer fix.
This task authorizes no production access, deployment or merge.

Reuse immutable source/version/document bodies and existing verified
`c0_project_source_snapshot_v1`/history plus immutable part receipts. Add reusable
Core reading/listing/history/resolution with current Reader authority, explicit
space selection, bounded metadata pagination, exact parent/version/order/offset/
hash validation and no chunk concatenation. A pending snapshot never replaces
the last complete snapshot. No new database model or widened extraction limits.
Core changes require a fresh immutable patch release and subsequent app pin/lock
adoption; preserve all prior releases and deployed predecessor identities.

Use the existing allowlisted Markdown renderer for source Markdown, plain text
for other extracted formats, headings/TOC, provenance/history and immutable
citation links. Unified All knowledge/Articles/Sources navigation groups explicit
provenance paths without fetching bodies or inferring product versions. Parse
large Markdown away from the UI thread and yield during DOM construction;
selection/access generations must invalidate all late work.

Prefer one existing REST upload for text within extraction limits, preserving
external identity, retry reconciliation and exact readback. Explicit legacy
multipart tests still exercise three or more real source parts and snapshots.

Acceptance order: green exact-main baseline; failing feature regressions;
Core/API/security/history/integrity implementation; formatted source reader;
unified bounded navigation and deep links; genuine unattended Playwright with
HTTP/PostgreSQL/worker/existing signed identity fixtures; full local candidate,
Core publication/adoption, exact image/both-native/privacy/scan gates; latest-main
rebase and final validation; reviewed unmerged PR. Synthetic data only. New
Playwright coverage is mandatory and does not use the older interactive waiver.
Record actual counts, timings, SHAs and limitations after execution.

### Full-document development checkpoint

Exact base e30bb449b165cac4a0c4b8cafaf950f64ed0675c full40723318218 now
passes both native jobs and merge gate; independent downloaded proof/audit follows.
Local base passes2303 Python/PostgreSQL/packaging,197 pinned-Node24 controllers,
21 Robot checks and schema/shell/docs. Production remains untouched.

Initial Core7247ead full40727801573 local reports2313 passes/two installed-probe
failures: the added assertion compared a UUID to the ingestion receipt string.
The isolated local run reproduces the same two failures; no release is published.
Corrected probes plus full-document/ingestion regressions and actual wheel/archive
installation pass68. They cover pending-parent denial, part-to-parent resolution,
legacy immutable receipt reuse, exact hashes/offsets, current grants and history.
A5000-source actual summary page returns50 items/no bodies in22.46ms locally.

Development UI passes202 controller cases and six genuine Playwright scenarios
using loopback HTTPS, signed test SSO, actual REST/MCP/PostgreSQL and a standalone
worker.377950-byte/three-part fixture: directory282.41ms, initial document2095.02ms,
Markdown rendering1213.40ms. These measurements are single local samples, not an
SLA or final frozen-source acceptance. Core publication, pin/lock adoption,
final full/native/browser/privacy/scan gates and an unmerged PR remain mandatory.

### Corrected Core native synchronization

Core7a6a601 passes the complete2319-case local suite and CI local/released-Core/
producer/scans. Debian upgrade passes21. Rocky reports25 passes/one failure/three
expected skips: the existing OAuth Administration browser reads the transient
"Loading people and application requests…" before "Application approved.".
The server mutation performs its refresh before that terminal feedback. The same
Administration source passes both native jobs at7247ead; this failure is retained,
not waived. Failed downloaded XML/Pino artifacts have zero OAuth-query candidates.

A test-only correction now waits for terminal approval/permission feedback before
retaining the existing assertions and actual server readback phases. Focused
native-helper/privacy tests pass68. Core package bytes and runtime Administration
code are unchanged; a fresh full exact-source run is required before0.35.2 can
be published. All six genuine document browsers also pass the534750-byte fixture
with a code fence crossing actual storage parts; a timer probe observes56 ticks
and59.9ms maximum tick gap during954.9ms rendering on this local sample.

The independent downloaded exact-main audit now passes: Debian upgrade 21,
Rocky installation 26/three expected skips, all eight native browsers, eight
privacy guards, 32 accessibility contexts, three OAuth-query artifacts with zero
candidates and five actual SARIF/SBOM pairs. The full promotion verifier passes
for the exact e30bb449 source. Fresh Core candidate 0e35adda full run 40742034125
is pending. A separate 5,000-logical-parent disposable PostgreSQL benchmark
returns 50 metadata summaries in 2,942 ms at offset 0 and 2,903 ms at offset 4,950;
no document bodies are read for directory construction.


### Directory scale regression before Core publication

Exact Core candidate 0e35adda full [40742034125](https://github.com/Stell0/ns8-czero/actions/runs/40742034125)
now passes all required jobs and the independent downloaded artifact audit:
Debian upgrade 21, Rocky installation 26/three expected skips/all eight browsers,
eight privacy guards, 32 accessibility contexts, three zero-query artifacts and
five actual SARIF/SBOM pairs.
It is not published: a new 10,000-parent regression reproduces the existing
five-second SQL timeout in directory discovery. The first failed fixture also
exposes an oversized foreign-key cleanup statement; bounded cleanup now succeeds.
No database deadline, extraction bound or deployed artifact is changed.

Keep UUID join columns indexable and use an equality anti-join for importer part
exclusion. Actual PostgreSQL EXPLAIN shows primary-key lookups and a hash
anti-join. The 10,000-parent fixture returns 50 summaries/no bodies in 562 ms at
offset 0 and 505 ms at offset 9,950; the single-case regression passes. All 17 full-document cases now pass together, including repeated-import
fixture state: 10,000 parents return 50 summaries in 808 ms at offset 0 and
523 ms at offset 9,950, and bounded cleanup succeeds. Fresh full exact-source
Core acceptance remains required before publishing 0.35.2. The last complete application producer suite
passes 2,321, pinned Node passes 204 and all six actual document browsers pass in
82.33 seconds, including independently consuming the genuinely delayed response
before checking revoked document/provenance/technical content remains empty.


### Published Core and application adoption

Core3fb900e25cced88c25ca8b8dd2148ae911a31f00 passes the isolated complete2,320-case
suite and exact full[40774328932](https://github.com/Stell0/ns8-czero/actions/runs/40774328932).
Independent downloaded reports verify Debian upgrade21, Rocky installation26/
three expected skips/all eight browsers, eight privacy guards,32 accessibility
contexts, three zero-query artifacts and five actual SARIF/SBOM pairs. The full
promotion verifier passes. No deployed predecessor or production setting changes.

Immutable[core-v0.35.2](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.35.2)
is published by[40782732045](https://github.com/Stell0/ns8-czero/actions/runs/40782732045),
including actual supplied-distribution installation/migration/rebuild checks.
Downloaded assets match SHA256SUMS:

- wheel: `1c6c5ff4250e2df4dca2064c2e61983f993cbd49059256237b3235ef588ab6f9`
- archive: `7699c0acbb52aa3e3b0b8a4892e4337024c09b8809548790935cc3fa7c2f6a1a`

Reproduction requires the commit SOURCE_DATE_EPOCH1793223806. An initial local
supplied-artifact run omitted it and reports seven passes/one rebuild mismatch;
that incorrect invocation is retained. The corrected exact-epoch run passes all
eight supplied wheel/archive tests, including identical rebuild hashes.
The publication workflow uses the correct epoch and passes. No asset is replaced.

App0.55 adopts released Core0.35.2/tag3fb900e, >=0.35.2,<0.36 and a regenerated
frozen lock; no unrelated dependencies change. Native candidate expectations
advance to0.55 while all three actually deployed31b0c85 predecessors remain
frozen at app0.54/Core0.35.0. All207 pinned-Node controllers and six genuine
Playwright scenarios pass, including malformed optional metadata, snapshot
provenance, visible citation evidence and metadata-independent legacy source links.
Latest535KB sample: directory266ms, initial document2080ms, rendering944ms,
57 browser timer ticks and56.5ms maximum tick gap during rendering.

The independent frozen-lock consumer uses non-editable released Core0.35.2 from
Git3fb900e outside the checkout and passes all2,322 Python/PostgreSQL/packaging
cases in1,293.21s, with zero failures/skips and the existing Authlib warning.
Node207, genuine browser6, Robot dry-run21, schema, shell, actual Renovate API,
295 documentation links and the public contribution scan pass. The primary-agent
full staged diff review is complete; it is not an independent human review.
Exact application PR CI/native/browser/privacy/scan acceptance remains required;
record its actual result in the PR after execution. No merge,
production operation or additional real-data ingestion is authorized by this task.

## Project plugin 1.2 acceptance repair

PR41 adds protected-project discovery to the existing instance-bound plugin. Repair
the skill inventory, standalone-fork references, runtime asset copies/allowlist and
native downloaded-archive contract together. Preserve the original failed source
and its evidence; rebase a separate candidate on reviewed main64b183e and retain
both histories when updating the PR. Schema0022 and the installed runtime remain
the predecessor; the security prerequisite below adds a compatible Core patch.

Acceptance requires the complete unchanged-main baseline, focused package/fork/
browser-helper regressions, the complete candidate suite, exact ready-PR full
CI/native/privacy/scan proof, review and promotion verification, then successful
main validation/publication. Verify connected project discovery read-only; do not
initialize a project, install schedules or deploy merely to test the package.
Private ChatGPT installation and external-agent execution remain distinct from
generated-archive and native-browser acceptance. Keep the installed31b0c85 trio
and existing waivers unchanged. Focused repair validation passes161 cases and292
local documentation links; both changed/new skill frontmatters validate. An
independent developer review passes98 non-database cases and forward-checks
missing tools, missing projects, separate scheduling authority and uncertain-call
recovery without a blocking finding. These checks are not live model or native
acceptance. Final exact-source full/native/main results are recorded on
[PR41](https://github.com/Stell0/ns8-czero/pull/41) after execution.

An actual local default released-Core image passes runtime/legal-content audits
and generates the1.2.0 plugin with all11 expected files; the native archive guard
accepts that output. The existing connected host exposes the project catalog;
profile/authorized-space discovery and the operator-selected protected project's
manifest/diagnostics reads succeed, with no project writes. Scheduling/monitoring
remain disabled and no successful external daily/weekly run is reported. This
proves current-host read-only discovery, not automatic skill activation or
unattended execution. No connection replacement or scope change was performed.

### Inherited Authlib security prerequisite

Exact repair8a628a9 is blocked by the mandatory app-image critical-vulnerability
gate in [40672102241](https://github.com/Stell0/ns8-czero/actions/runs/40672102241).
The newly reviewed [upstream advisory](https://github.com/authlib/authlib/security/advisories/GHSA-6v38-4h7w-rj9h)
includes the inherited Authlib1.8.0 pin. An actual signed positive/empty-signature
negative regression reproduces acceptance of an unsigned JSON payload on1.8.0.
Do not suppress the finding or override immutable Core dependency metadata.

Core0.35.1 pins Authlib1.9.1, preserving joserfc1.7.5, all other pins, schema0022
and authority semantics. Exact6a11469794d5070af469343aa63715fd0e727d98 passes
[full40673116010](https://github.com/Stell0/ns8-czero/actions/runs/40673116010):2303
Python/PostgreSQL/packaging, 197 Node24 and21 Robot cases. Local complete producer
validation independently passes2303 cases in1140.44s without skips. Independent
developer security/identity/OIDC/renewal/source review passes142 focused cases.
Actual downloaded native/scan audit passes Debian genuine31b0c85 upgrade21 and
Rocky installation26/three expected skips, all8 browsers/privacy guards,32 numeric
accessibility contexts,3 zero-query artifacts and5 scan/SBOM pairs. The app-image
SBOM confirms Authlib1.9.1. Exact-source full promotion verification passes.

Immutable [Core0.35.1](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.35.1)
points to that source; [publisher40680486868](https://github.com/Stell0/ns8-czero/actions/runs/40680486868)
passes verify/publish. Actual downloaded wheel SHA256
`9977a43a5b469089e889b769e92496a40f735c834d0b367d13a8d4456c5939f8` and source
`70832d916b2c83110ac6406e8f5e641d125a7a84cedaf1a3895bcafe99f20f15` match
published checksums. Eight actual supplied-artifact checks independently pass
installations, reproducible rebuild and fresh/repeated PostgreSQL migration in94.56s.
The bridge retained the existing released default until verified publication;
packaged Core bytes remain frozen afterward.

The app now adopts the immutable0.35.1 tag/lock with >=0.35.1,<0.36.0 and matching
patch-only updater bounds. Final released-consumer/full/native acceptance, review,
promotion verification and actual main publication remain mandatory, with executed
results recorded on PR41. No deployment is part of this prerequisite. Freeze the
installed31b0c85 trio throughout;0.35.0 artifacts and historical evidence remain.

## Seven-day remembered website login — deployed acceptance

Base: original main `f317036`. Reviewed/approved [PR42](https://github.com/Stell0/ns8-czero/pull/42) is regularly merged at `31b0c85a71743ab6dcdb04c12ac18dd4c1500722` and the dedicated instance accepts Core 0.35.0 / app 0.54.0 / additive schema 0022. Preserve the historical `c2280f5` trio used for this genuine upgrade; the next genuine predecessor is the [installed `31b0c85` trio](#remembered-login-deployed-runtime-and-frozen-predecessor).

- First-party GET/POST `/auth/sign-in`, unchecked remember choice, five-minute one-use persisted intent and Secure browser binding; exact Origin, bounded form and duplicate checks precede OIDC. Compatibility `/auth/login` remains ordinary except for an already staged background flow.
- Provider-attested offline access and matching authenticated identity precede remembered issuance; failure offers ordinary sign-in. Seven-day browser inactivity is fixed, opaque cookies and encrypted credentials remain server-managed. Existing sessions stay ordinary.
- Successful authenticated website responses slide the browser deadline. Public/failed/MCP requests do not. Transactional current-role/native/session checks prevent logout or revoked authority being revived. Browser and connection inactivity policies remain independent, including explicit background consent from a remembered browser. Ordinary grants remain finite.
- Controlled-clock expiry/rolling/restart, one-use/CSRF/account-switch/provider failures, real PostgreSQL concurrency/revocation, profile isolation, native real offline issuance/cookies/update/restore and artifact privacy pass. The unchanged-main baseline, Core publication, immutable dependency adoption, exact ready-PR/main acceptance and operator-approved dedicated update are complete.

The exact unchanged-main baseline `f317036` passes [full acceptance 40495377796](https://github.com/Stell0/ns8-czero/actions/runs/40495377796), including independently downloaded native/privacy/scan artifacts and promotion verification.

Core source `254fd3fb817a7eb98fa22b10d1e20b33619af344` passes 2,275 local Python/PostgreSQL/packaging cases and [full acceptance 40518599847](https://github.com/Stell0/ns8-czero/actions/runs/40518599847). Actual downloaded reports pass Debian genuine upgrade (21), Rocky installation (26/three expected skips), all eight browser workflows, eight privacy guards, 32 numeric accessibility contexts and three OAuth-query artifacts with zero candidates. Five actual SARIF/SBOM pairs and independent exact-source promotion verification pass. The bridge tests app 0.53 with producer Core 0.35; they do not establish the new website flow.

Immutable [Core 0.35.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.35.0) points to that source; [publisher 40529304349](https://github.com/Stell0/ns8-czero/actions/runs/40529304349) succeeds. Downloaded wheel SHA-256 `389b3a3f1b781d906e202e26af6f5d7e1cdc34e5764e6265828899167cd3b694` and archive `0d15addec1a9e0c8785342583fe4d3d76e977c13836e2226569064a12c7bf07b` match published checksums. Eight supplied-artifact checks pass independent installations, reproducible rebuilds and fresh/repeated PostgreSQL migration. The app now pins that released tag/commit, `>=0.35.0,<0.36.0`, frozen lock and matching patch-only Renovate bounds.

App producer source `1dc0b0a` passes 2,298 actual Python/PostgreSQL/packaging cases, 197 Node 24 controller cases, immutable administration UI build, schema/shell/docs checks and 21 Robot dry-run cases. Final adoption `760d543` and repaired feature source `aa9bfd0452ff9bf704a287c6db0ca460453c6deb` independently pass the complete 2,298-case suite against fresh frozen-lock installations of released Core 0.35.0, with no database skips and verified installed Git provenance outside the checkout.

Exact ready-PR [full40541383069](https://github.com/Stell0/ns8-czero/actions/runs/40541383069) and merged-main [full40581381116](https://github.com/Stell0/ns8-czero/actions/runs/40581381116) are completed/successful, including canonical main publication. Main's tracked tree equals the accepted PR tree. Actual main CI passes 2,298 Python/PostgreSQL/packaging cases, 197 Node24 cases and 21 Robot dry runs. Downloaded reports pass Debian genuine upgrade (21), Rocky installation (26/three expected skips), all eight browser workflows, all six remembered-browser recovery stages, eight privacy guards, 32 numeric accessibility contexts and three OAuth-query artifacts with zero candidates. Five actual SARIF/SBOM pairs, three installed image identities, independent artifact audits and exact-source promotion verification pass. Preserve failed earlier candidates and their evidence; `88fa9bc`/`4d64102` are not accepted sources. The browser correction keeps `strict-origin` on the navigation form, exact Origin checks and `no-referrer` on the provider redirect.

## Remembered login deployed runtime and frozen predecessor

The operator approved PR42 and the supported C0-only update. Actual installed source `31b0c85a71743ab6dcdb04c12ac18dd4c1500722` runs app **0.54.0**, released Core **0.35.0**, schema **0022_remembered_browsers** and pgvector **0.8.7**. All three images retain the immutable tag `ci-31b0c85a71743ab6dcdb04c12ac18dd4c1500722-40581381116-1`:

| Image | Verified installed digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:d364bd089a5b21540a7a387f08f70f55a16a8ccaf437c6e52275cf694ffb1ecc` |
| `ghcr.io/stell0/czero-app` | `sha256:c4d4abfa87eaa2c6dfaee7ac374f602ca9369b0e638cb3dc4fdc78d2ed6ce09c` |
| `ghcr.io/stell0/czero-postgres` | `sha256:8f6cad78954186603bbf824f01bdbe77ae75122167cd1f32c5a393839c7c04c7` |

Freeze this trio for the next genuine upgrade. Documentation-marker sources do not replace installed identities. Keep the [previous `c2280f5` trio](#wikiplant-deployed-backend-and-frozen-predecessor) and earlier historical evidence available.

Fresh registry reads verify all six main/latest aliases and all three immutable candidate identities. A scoped C0-only backup and actual full backup-data integrity read pass; all backup-plan settings are restored. The targeted update and supported dedicated-manager restart both pass exact installed image/revision checks, trusted HTTPS readiness, schema checks and timer health. Before/after observers preserve all **32,795 original stable rows across 40 domain tables**, settings, authentication/retrieval hashes, schedules, mounts and ten unrelated module identities. The live original-file corpus is empty; nonempty original recovery remains covered by disposable acceptance. Migration 0022 adds one authentication table and three columns, with original columns retained.

The retained ordinary session stays ordinary, and fresh compatibility sign-in stays ordinary. Read-only owner REST/profile and five protected Wiki reads pass before/after update and restart. Real-provider remembered sign-in verifies the unchecked form, null-Origin rejection, explicit offline issuance, matching account, encrypted server authority, a Secure/HttpOnly/Lax persistent seven-day cookie, rolling renewal and cookie-jar reload. That remembered session survives the dedicated-manager restart. Signing out only the new test browser rejects its old cookie; the existing connected MCP profile still works afterward. Three original background grants retain their fixed fields, including scopes, allowing only normal activity/refresh-generation changes. The connected account/profile contract and four authorized-space discoveries remain unchanged. No knowledge, project or research-schedule writes are part of this acceptance.

Each bounded root app-journal window contains **38 actual entries**, with successful health/profile/guide/native-callback/token/MCP controls and zero OAuth-query, issued-secret, generic-credential, JWT or traceback candidates. Route and domain configuration remain unchanged. Empty log-collector responses are not privacy evidence; these root-journal windows supply the actual request controls. Controlled-clock tests establish the seven-day inactivity boundary; live checks establish offline issuance, renewal and retained sessions through restart. Other live roles, provider/client revocation and destructive recovery retain their disposable evidence. Existing CPU-quota and interactive Playwright waivers remain unchanged. No stable NS8 module release is claimed; broader client/scheduled/research acceptance remains separate.

## Roadmap

### Active work and remaining acceptance

The opening sections track the native OAuth callback repair and retrieval-evidence
producer work. Knowledge compilation has implemented workflows but failed measured
quality gates; its production rollout is not accepted. Preserve separate Core
publication, released-consumer adoption, source/full/native and live deployment gates.
The release-readiness phases below retain packaged-skill web and real scheduled-client
acceptance requirements. Source implementation is not proof of those outcomes.

Reusable ingestion samples are implemented. Their original implementation checkpoint
is preserved below; use current samples and skills for new adapters.

<details>
<summary>Historical ingestion implementation and acceptance plan</summary>

<a id="active-implementation--reusable-ingestion-samples"></a>

### Historical reusable ingestion samples checkpoint

The operator approves the full GitHub project/contributor/document pipeline as
an instance-neutral sample and a dedicated ingestion OAuth connection. Add a
development-only Python package under `samples/ingestion`, with shared SDK/MCP,
identity/space checks, credential/state storage and source-ingestion helpers.
Keep GitHub discovery, metrics and mapping separate. Preserve stable external
keys, immutable snapshots, source-version hashes, receipts, partial coverage,
bounded work and independent readback; unchanged reruns must not duplicate data.
Wiki summaries are opt-in. Existing pages require matching private receipts for
ID/revision/body; preserve manual edits and unrelated pages without adoption.

Local jobs live under ignored `.local/ingestion/<job>` with a runnable wrapper,
instance `.env`, source configuration, private credentials, snapshots and state.
Use a dedicated preapproved OAuth public client with exact loopback callback,
explicit background consent, locked atomic rotation and no unattended interactive
fallback. Normal sync requires explicit apply and Read/Write; Admin bootstrap is
separate and never overwrites incompatible global schemas. Preserve the original
external GitHub directory and migrate its configuration/state without live writes.

Add the `c0-ingest-sources` repository skill, public adapter notes and synthetic
regressions. Future ingestion first reads samples, implements reusable adapters,
uses private jobs, verifies actual receipts, removes private material from the
complete contribution and opens an upstream PR using nethserver-pr. Register
reusable fork files explicitly and keep all samples out of runtime images.

Acceptance requires full latest-main baseline and candidate checks, GitHub and
OAuth/state/identity/space/retry privacy regressions, actual disposable MCP/DB
read/write/conflict/denial/index/readback tests, independent package installation,
full image/both-native CI and inspected artifacts. No Core/schema/runtime changes,
production deployment, live reingestion or installed schedule is part of this phase.
Record completed evidence and limitations before claiming acceptance.

Implementation checkpoint: the generic package is 0.1.0 and runs independently
of Core/the application. Current focused source/client/private-job tests and
actual disposable SDK/OAuth/PostgreSQL, immutable evidence, lost-reply recovery,
conflict/Reader denial and revocation tests pass. Actual wheel and source-archive
installations outside the checkout pass. A copied existing private job validates
offline without content writes; original files remain unchanged and its dedicated
Read/Write client is approved, with one-time user login pending. No source data,
instance configuration or credentials are included in this contribution.

Exact original-main baseline `09c10d3` passes full40233296553 and independent
downloaded artifact inspection: Debian upgrade21, Rocky installation26/three
expected skips/all8 browsers, 30 accessibility contexts, three OAuth-query
artifacts with zero candidates and five scan/SBOM pairs. Local broad regressions
pass 2043 cases at preserved candidate `67c57d5` after moving disposable packaging
files out of quota-limited `/tmp`; the failed attempt is retained privately.
Final review adds opt-in Wiki publishing and receipt guards; its 75 focused cases
and two actual SDK/database cases pass, including preserved human edits. Fresh
frozen-candidate full local/CI checks and PR review remain required. These tools do not replace the
accepted runtime images or establish actual scheduled-client acceptance.

</details>

Work through these phases in order. Each phase needs observable results before it is called complete; there are no promised dates.

| Phase | Status | What people should get | Done when |
| --- | --- | --- | --- |
| Shared knowledge foundation | Implemented and accepted under development gates | Wiki, original sources/citations, structured records and graph, indexed retrieval, users/protected spaces, browser/REST/MCP and revocable OAuth | Recorded local, released-Core, image, both-native and dedicated-instance acceptance remains valid |
| 1. Make the first-use experience clear | Active documentation/skills release work, M21 | Someone can understand C0, install an instance, connect the right account, use its skills and fork it from public guidance | A fresh user completes setup, first source, cited read and authorized edit without a private maintainer runbook; packaged-skill web routes are actually exercised |
| 2. Prove the assistant workflows | Remaining release-readiness work | Repeatable use with connected clients, including unattended maintenance | Fresh scheduled read-only and read/write tests verify results after token expiry, renewal, denial and conflicts; Claude/Grok routes receive their own C0-specific tests |
| 3. Publish a release operators can trust | Gated | A clearly supported version, installation/upgrade guide and reviewed skills/packages | Required release checks pass, security findings are dispositioned, retrieval quality is measured for the claimed workload, and publication/release scope is explicitly approved |
| 4. Grow the application foundation | Later, separately planned | More domain applications, richer agent memory and optional workflow integrations | Each extension has its own scope and data/authorization/recovery acceptance; broader agent-memory work follows session-usability acceptance and Windmill follows M21 |

### What already works

- A person can read knowledge and use the explicit source-upload workflow in the browser; an authorized assistant can search/read through MCP and perform requested knowledge changes.
- Sources and Wiki pages retain one current complete content generation, with stable logical IDs, monotonic revision counters and current exact citations; evidence, records and graph relationships stay within their selected space.
- Verified users, Read/Write/Manage roles, protected-space grants, application approval, exact disconnect and persistent blocking are implemented.
- Text retrieval works without a model provider. Optional embeddings/scoring and a reusable Python Core support applications that need more.
- NS8 packaging, disposable tests, CI image/native checks and managed fork/Core update mechanisms are implemented.

These capabilities are available in a tested **development candidate**. They do not by themselves establish a stable module release, every client's compatibility or successful unattended agent execution.

### Next acceptance work

1. Complete the public documentation and skill walkthrough, including actual ChatGPT web package installation/account binding and the intended private/managed routes. This documentation refresh clarifies the product and fork story; it does not claim those runtime/platform gates passed.
2. Maintain the fork workflow: latest original C0 main, rebased development branches, green base tests plus retained feature regressions, tested upstream contributions and current Codex-facing plugin/connector contracts.
3. Resolve the scheduled-task execution blocker with a visible run trace or controlled reproduction. Verify a read-only run first, then one authorized Wiki update with exactly one new revision and readback. Record real errors rather than interpreting an empty completed run as success.
4. Keep the working ChatGPT connection and verify Codex independently. A 25 October operator setup proves a dedicated Codex OAuth connection with an exact loopback callback, current profile/protected Wiki reads and an administrator-only read. It does not prove Codex content writes or scheduled execution. Claude and Grok publish MCP connector routes; their C0-specific end-to-end acceptance is still pending.
5. Finish remaining model-evaluation, actual-provider retrieval-quality and security/release obligations. Runtime changes require their own full acceptance and deployment loop. Stable tagging, public plugin-directory submission and workspace-wide rollout each need explicit scope and approval.

Use [release-readiness requirements](docs/release-readiness.md) for the remaining gate definitions. Its older implementation checkpoints and unchecked historical rows must be read together with the newer accepted-runtime evidence below; they do not undo passed runtime gates. No automatic knowledge-maintenance agent or native Wiki cron handler is proposed as a substitute for testing the external assistant workflow.

## Agent instruction maintenance — 11 November 2026

The instruction cleanup uses original main
`bdb928e62a057309d7822282fd7c505303d3bbfb`. AGENTS retains durable rules and
historical anchor aliases; its complete prior text is preserved in
[the instruction checkpoint](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026).
Current runtime selection now points to the accepted delivery record. Developer
skills distinguish runtime end-user assets and follow risk-based validation.
The initial review covered all ten developer and five end-user skills; its two
confirmed developer-skill contradictions were corrected. Related maintained setup,
development and release guidance needs no package/version or scope change.
Base and candidate documentation/fork checks each pass 17 cases; maintained
local-link checks pass, and both edited skills pass frontmatter validation.
The original cleanup diff is entirely in the existing Git-only documentation
allowlist. The follow-up adds instruction review as a PR readiness/merge requirement,
a matching contributor-skill step and a registered PR template. The template is a
new path outside the documentation allowlist, so the combined PR requires full
acceptance under the unchanged CI policy. Actual PR checks and the C0 merge gate
remain required. This changes no runtime, dependency,
connection, schedule or accepted installation identity.

The subsequent developer-skill review adds shared implementation practices for
focused changes, caller/contract tracing, behavioral tests, domain errors, bounded
external work, dependency decisions and private diagnostics. Core guidance keeps
released migrations immutable and requires populated-predecessor checks; feature
guidance routes frontend work to Nebula. Project guidance separates candidate
implementation from live capability checks. Contribution review checks final diff
scope, and collector-specific prose is removed from unrelated skills. Existing
shared references and skills are already registered for standalone consumers.
Evaluation and semantic-maintenance workflows retain their authority and evidence
boundaries; these coding rules do not impose development checks on unchanged runs.
The final local documentation/fork/CI-policy selection passes 160 cases and all
ten developer skills pass frontmatter validation. Link checks include the standalone
consumer. No model-driven behavioral evaluation is claimed; full CI remains pending.

The subsequent CI policy change narrows documentation classification to reviewed
developer assets and verified documentation-only registry additions. Draft runtime
PRs receive fast feedback; ready sensitive PRs, manual full runs and releases keep
full acceptance. Draft/fast proofs cannot authorize sensitive merges. Existing
frozen full runs remain preserved. This CI/policy implementation itself requires
full native acceptance before merge; no release or deployment is implied. Focused
policy/promotion/documentation/fork checks pass 186 cases, including actual Git
registry changes and the documentation checker. Full exact-source CI remains pending.
After the released-Core adoption merged, the successor candidate starts at original
main `505b8ee54b5ce79bf873145e36f12dc7d5ec7c3e`. Preserve the earlier candidate
`08a207e21fc9b04995880a259ecade5b0dece7db` and its full acceptance run; the
successor requires its own current-base validation and full native acceptance.
The preserved first CI candidate encounters HTTP 404 for Debian's floating
genericcloud image before VM boot. Native CI now selects the official dated
20261103-2651 image and its published SHA512SUMS through the shared runner's
existing URL override. Both native suites remain mandatory; no failed result is
waived and the original runs remain available.
The access-role repair subsequently merges as original main
`a106f188d362fa02574972662f84bb3fc93774af`. A further successor preserves its
cumulative role labels, browser regressions and identical Debian image pin.
Keep `b77bc6a68d1cf54823a19114a22129871ff3240d` and both full runs frozen;
the current-base successor requires its own focused and full/native acceptance.
Cross-space reference PR119 then advances original main to
`08e979c4ae285bed03953cf58c6a0a63ebc8888c`. Preserve the previous candidate
`f474737bc8d74bfc6ad3713314d3dd5824cb1e2b` and its full run43119794696.
The next successor retains the cross-space contracts, migration0038, plugin1.10,
released consumer lock and new feature regressions. Repeat exact-source acceptance.
Documentation closeout PR124 advances original main to
`1e99d7d0ed3912ebbfc3a925f9eec961bc8170ad` and records the accepted app0.64
installation. Preserve candidate `401336b681ff64898bb937add88f8e12ca026dae`,
successful full43126746286 and its exact-source promotion proof. The successor
resolves instruction conflicts against that closeout, retains its deployment
evidence and repeats the required current-base checks before merge.

## Current baseline

The accepted dedicated installation is app **0.64.0**, released Core **0.46.0**,
schema **0037**, source `a106f188d362fa02574972662f84bb3fc93774af`.
Its [accepted deployment record](#native-oauth-accepted-deployment)
contains installed immutable tags/digests, supported update/restart acceptance and
preservation evidence. Those installed images are the next genuine predecessor;
retain the actual app0.63/Core0.45 predecessor, historical app0.61/Core0.42 and
all earlier frozen images and evidence.

Source versions are separate: use `app/pyproject.toml` and its committed `uv.lock`
for the app and released Core dependency, `packages/czero-core/pyproject.toml`
and its migrations for producer Core/schema, and the plugin manifest for its
package version. These source capabilities do not establish publication, consumer
adoption or live activation. Use the [verified installation candidate](docs/installation-candidate.md)
for published image selection. No stable NS8 module release is claimed.

<details>
<summary>Historical baseline checkpoint</summary>

### Historical remembered-login baseline

Accepted dedicated runtime: app **0.54.0**, released Core **0.35.0**, schema **0022**, source `31b0c85a71743ab6dcdb04c12ac18dd4c1500722`. Freeze its three [installed image digests](#remembered-login-deployed-runtime-and-frozen-predecessor) as the next genuine upgrade predecessor. Documentation/main-marker images do not replace it; prior installation records remain preserved below.

Prior runtime main `05ce22c` passed full [40106287084](https://github.com/Stell0/ns8-czero/actions/runs/40106287084), canonical publication and independent actual native/privacy/scan audits. Reviewed documentation closeout PR35 merged as `f735004`; its [main40137756852](https://github.com/Stell0/ns8-czero/actions/runs/40137756852) and exact-source documentation promotion verifier pass. Original dirty checkouts, recovered M20 worktrees, drafts and immutable artifacts remain preserved.

</details>

## How development proceeds

Agree the behavior and acceptance, implement one focused change in the right layer, verify it with disposable tests, review the PR, and follow the [CI policy](docs/ci-policy.md). Current CI policy uses fast PR checks and automatic native acceptance for sensitive changes; reviewed allowlisted UI can request it on demand. C0 permits protected automatic regular merge without mandatory human approval. Full native proof and explicit live authorization remain required for releases and production deployment. Internal and external contributions follow the same risk classification; see [contributor requirements](AGENTS.md#tests-are-part-of-the-feature). Existing interactive Playwright and CPU-quota waivers remain unchanged.

The detailed plan and evidence below preserve decisions, failures, exact sources, image identities and test results. Older “current” or “pending” wording describes its checkpoint; the Current baseline section and opening active-work records govern present work.

<details>
<summary>Detailed implementation plans and acceptance evidence</summary>


## Operator priority — people-first workspace access (24 October 2026)

## Approved people-first Workspace Access page

Status: implementation, exact-source distribution/native checks, dedicated-instance
acceptance and reviewed promotion pass. The current accepted runtime is app0.52 /
Core0.33 / schema0021 at frozen source `e384bed`; PR33 and PR34 are merged.
See the executed evidence and frozen image identities below. The following design
and preimplementation model are retained to explain the accepted behavior.

## Accepted runtime and promotion — 24 October 2026

The operator reviewed and approved PR33 followed by PR34, and separately
confirmed the existing ChatGPT web connection worked without manual reconnect
for more than 24 hours. [PR33](https://github.com/Stell0/ns8-czero/pull/33)
merged regularly as `cd17a02`; its
[main40101415111](https://github.com/Stell0/ns8-czero/actions/runs/40101415111),
canonical publication, full promotion proof and independently inspected native,
privacy and scan artifacts pass. This closes the outstanding web observation;
it does not establish scheduled-task interoperability.

The accepted application source is `e384bed641ac0bdc97212def22db521c0ab2e4c7`,
app **0.52.0**, released Core **0.33.0**, schema **0021_workspace_access**.
Its [full40093959067](https://github.com/Stell0/ns8-czero/actions/runs/40093959067)
and independent artifact audit pass: Debian genuine PR33 upgrade 21 passes,
Rocky installation 26 passes/three expected skips, eight real browser workflows
and privacy guards, 30 numeric accessibility contexts, ten independently typed
access stages, three actual query artifacts with zero candidates and five
scan/SBOM pairs. The local final released-wheel consumer run passes 1963 actual
Python/PostgreSQL/packaging cases without database skips in 600.14 seconds;
Node24 controllers pass 185, with schema/shell and 21 Robot dry runs. The native
browser results establish workflows for Reader, Editor and Admin accounts,
including administrator approval/decline, exact disconnect, persistent blocking
across repeated sign-in and actual service restart, and unblock without old-token
resurrection. Sibling/other-user controls and protected-space boundaries pass.

After PR33 merged, integration head `cc8c2cf` merged only the approved ancestry:
its entire tracked file tree equals the reviewed and deployed `e384bed` tree.
[Full40101567741](https://github.com/Stell0/ns8-czero/actions/runs/40101567741)
and independent actual artifact audit pass the same 21/26/three-skip, eight
browser/privacy, 30-accessibility and ten-stage gates. Exact current-head/base
promotion verification passes. [PR34](https://github.com/Stell0/ns8-czero/pull/34)
merged regularly as `05ce22c26055cf321e8a3d90471406dbc11e99dd`, retaining those
source commits and the identical accepted file tree.

Resulting main [40106287084](https://github.com/Stell0/ns8-czero/actions/runs/40106287084)
is completed/successful at `05ce22c`. Actual main logs confirm 1963
Python/PostgreSQL/packaging passes in 714.95 seconds, 185 controller passes with
no skips/failures and 21 Robot dry runs. Producer/released-Core builds, image
identity checks, five scan/SBOM pairs, both native distributions, artifact audit,
merge gate and canonical publication all succeed. Independent downloaded reports
confirm Debian21, Rocky26/three expected skips, all eight browser/privacy workflows,
30 numeric accessibility contexts, ten access stages and three query artifacts
with zero candidates. Exact-source promotion verification passes. Six fresh
registry reads verify all three main/latest aliases against the published source
and digests. The accepted dedicated runtime remains frozen at e384bed.

### Dedicated-instance acceptance and frozen predecessor

Only the dedicated C0 instance was updated using the supported canonical native
action after a C0-only backup and actual backup-data integrity read. Update
completion took 24.71 seconds. Readiness, the installed module/app/database
identities, route, certificate, worker and timer checks pass after update and
supported full-manager restart. Preserve this accepted installation and tag as
the next milestone's genuine upgrade predecessor:

| Image | Frozen digest |
| --- | --- |
| Module | `sha256:3e16e819787850a4a9f90016a946a3bbb71c3d8bb5073c42b22ac344df68f2fa` |
| Application | `sha256:90903768ec49e84d9439530da48864eebe1bdb9a0a5d5cee59ae64be19200d11` |
| PostgreSQL | `sha256:0907ed3c57b4d2b34d84d2a168a7718b143fd07f37b0a9048fa1a7f50aee7dbe` |

All three revisions are `e384bed641ac0bdc97212def22db521c0ab2e4c7`; the canonical
candidate tag is `ci-e384bed641ac0bdc97212def22db521c0ab2e4c7-40093959067-1`.
Keep that tag available and unchanged while the installation references it.
Integration, main and documentation publications do not replace this accepted
runtime. Public examples use `https://c0.example.org`; private deployment
identities, credentials, raw journals and evidence stay outside Git.

Independent before/update/restart/final observers preserve all 40 original domain
tables and 247 original stable rows, existing column values, settings, mounts,
authentication/retrieval configuration, schedules, terminal jobs/attempts and all
nine unrelated instances, including each exact C0 action window. The additive
migration introduces only two columns, no new table. Original stored files and
active Shared Wiki/source lists are empty: metadata reads prove authenticated
access, without a claim of nonempty retained content evidence. One existing
background grant retains its fixed authority while normal activity and refresh
generation advance. No real user's permissions, block or application approval
was changed for live testing.

Live signed-in owner/browser, authenticated REST and current/legacy SDK profile
and repeated explicit-space Wiki/source list reads pass after update and manager
restart. Isolated owned grants prove exact disconnect: target access401 and
refresh400, sibling access200 and rotating refresh200; membership and client
approval remain unchanged. Both temporary read-only manual clients were disabled,
all their grants reject access and the owned browser session was logged out.
No fixture content or schedule was created live; destructive recovery and other
role browser workflows remain disposable.

The existing connected-tool path works without manual reconnect across a
measured 627-second window and the update/restart. A read-only server observer
separately proves two public refresh generations on the same original background
grant and native authority, with last use beyond the previously observed access
deadline; it does not inspect the user's raw credentials. This is distinguished
from the operator's separate more-than-24-hour ChatGPT web observation.

Bounded root application journals use the verified module UID and container:
90 entries from 13:40:45–13:47:50 UTC after update and 93 entries from
13:52:23–13:55:28 UTC after restart. Both windows have positive health, owner
profile, guide, authorization, token and MCP request controls. Actual OAuth query,
known-issued-secret, generic credential, JWT and traceback candidate counts are
all zero. Empty Podman logs are not used as evidence; host logging is unchanged.

The access-page implementation and persistent-connection observation are
accepted. This separate three-document closeout requires its own lightweight PR
and main gate and independent review. It changes no package or runtime input and
must not replace the accepted installation. Existing interactive Playwright and
CPU-quota waivers remain unchanged. M21 packaged-skill web use, quota-blocked
model evaluations, actual scheduled-client interoperability and vendor findings
remain separate release-readiness work. No stable module release is claimed.

## Existing model

This is the inspected preimplementation model; the settled interfaces and accepted
runtime above supersede its missing-API statements.

- AccessService owns persisted application roles, verified identity display metadata and explicit account blocks. Verified new users receive Shared Reader admission in the application. A block survives renewed/renamed sign-ins. The configured owner is always Admin and cannot be changed/blocked through this service.
- set_role invalidates every OAuth grant and native authority for the target, even on a same-role call. The UI must skip unchanged saves and warn before real role changes. Regrant does not restore old credentials.
- ClientOnboardingService holds bounded, signed-in, five-minute requests. Its current admin DTO has username/metadata URL/callback/scopes/approval, but no account ID, full name or safe action handle. There is no Decline operation.
- CimdClientService performs reviewed exact-metadata/client approval with digest and revision checks. Approval is application-wide for that exact client identity; it is not a user role or consent grant. Reapproval can invalidate that application's connections for other users. Existing UUID clients remain independent.
- OAuthGrantService exposes only first-party own-account connection listing and disconnect. It cannot currently list/disconnect another user's individual connection as an administrator.
- OAuth scopes are independent: c0:admin does not imply c0:read or c0:write. Protected-space grants further cap Reader/Editor access; application Admin has implicit access to all spaces.

## Proposed presentation

/admin becomes Workspace access. A pending-request count and jump link precede one main table: Username | Full name | Read | Write | Manage | Status | Actions. Group rows by stable account identity. People with actionable pending requests sort first, then other people by username; each person has a primary row, followed by relevant application/request/connection rows. Show application name beneath the username on those rows. Never merge client identities merely because names match. Unknown/unreviewed application names display Application awaiting review with a hostname as an origin cue, without fetching remote assets. Verified metadata review supplies the name.

Primary person permissions represent current workspace role: Reader=yes/no/no; Editor=yes/yes/no; Admin=yes/yes/yes; Blocked=no/no/no. An explicit Change permissions control offers these three presets rather than implying unsupported arbitrary combinations. The owner is labelled Owner with locked controls. Full name is verified display metadata, with an em dash when absent; it never determines identity or authority.

Application rows distinguish Requested, Consented and Effective using literal labels in each relevant permission cell. A pending request has no effective connection access. A connection's effective capability requires its consented scope AND current application role, and remains subject to the selected space; display a persistent note that the table is workspace-level and protected spaces need separate grants. Never infer broader scopes from Manage. Do not claim provider availability from saved connection metadata.

| Row/state | Meaning | Available actions |
| --- | --- | --- |
| Person: Access enabled | Current Reader/Editor/Admin membership, no statement about an application connection | Change permissions; Block user; Details |
| Person: Owner | Configured immutable application owner | Details |
| Person: Blocked | Persisted account block; no effective access | Unblock user (explicit role selection); Details |
| Person: No access | No membership and no explicit block, if a closed-admission Core consumer produces this state | Grant permissions; Block user; Details |
| Application request: Needs application approval | Exact client/callback not approved | Approve; Decline; Details |
| Application request: Needs additional application permissions | Client approved but requested scopes exceed its approval | Approve; Decline; Details |
| Application request: Waiting for user consent | Current exact application/callback/scopes approved; no matching consented connection yet | Details; dismiss the still-pending handoff through Decline if needed |
| Application connection: Connected | Locally valid, consented grant; show last use and session/background label | Disconnect application connection; Details |
| Application connection: Needs reconnect | Revoked, expired, policy-invalid or unavailable authority observed during this page session | Details; reconnect guidance; no fabricated durable history |

An expired/declined/disconnected request or grant disappears from refreshed active rows, with a clear action confirmation. Do not invent a permanent disconnected/declined audit ledger where none exists. If a person has both a usable connection and a request for additional permissions, show both so the pending request does not imply that current access stopped. Blocked users' stale requests cannot be approved to bypass the block.

Technical IDs, metadata URLs, callbacks, exact scope names, revisions and timestamps live in Details/Advanced; required application-origin and approval-impact information remains visible in the approval review. Advanced contains manual client configuration, metadata diagnostics and explicitly global Enable/Disable application controls. Protected-space management remains a separate clearly linked page. Jobs and schedules move to a separate Background work page; none are loaded by the access page.

## Action semantics

- Approve opens a focused review with verified application name/origin, requested permissions, current user permissions, selected application permission ceiling and affected-user warning if updating an existing approval. Preserve preview/digest/revision checks, current policy, exact callbacks and post-I/O authorization checks. Approval changes only the exact application approval. It never changes membership, issues tokens, adds scopes to existing tokens, grants protected spaces or automatically approves a blocked person. Preserve earlier approved scopes unless the administrator explicitly edits the application-wide ceiling under Advanced. The requester must continue and explicitly consent. If requested Write/Manage exceeds their role, offer a separate Change permissions action; never silently combine them.
- Decline cancels only that exact browser-bound pending handoff, after current Admin authorization and CSRF. It does not block the user, disable the application, disconnect an existing connection or prevent a fresh request. A stale/expired request returns a safe refresh-required result. The requester's existing handoff cannot continue after decline.
- Change permissions changes the person's application Reader/Editor/Admin role through AccessService. Warn that it invalidates all that person's application connections and requires sign-in/consent again. Manage additionally grants application-wide administration and implicit access to every protected space. Unchanged saves do nothing. Use optimistic state checks to reject stale saves.
- Disconnect application connection deletes only the selected user's exact grant, invalidating its access/refresh credentials. Keep membership, other grants including the same app's separate grants, app approval and space grants. Allow fresh consent later. Do not revoke shared native authority and accidentally break sibling connections.
- Block user persists the existing explicit block and invalidates all target authority through AccessService. It cannot block the configured owner. Repeated provider sign-in cannot restore admission. Unblock explicitly selects a role and does not restore old connections. Existing protected-space grants retain their current stored policy.
- Disable application is an Advanced, explicitly global action, distinct from user blocking and per-connection disconnect; enabling later requires fresh consent and does not revive old grants. No action uses the label Revoke.

## Missing API support and proposed additions

1. Extend the Admin account read DTO with explicit block state and a version/state precondition; bound and paginate rather than silently omit people beyond the current default 100. Keep current services and role/scope checks. Add an optional expected-state precondition to role writes without breaking existing callers.
2. Extend the Admin request DTO with stable account ID, full name, safe opaque request action handle, current role/block state and explicit application approval state. Add a narrow Admin decline method/HTTP endpoint which cancels only that handoff. Do not expose its cookie binding, raw hash, state, PKCE challenge or credentials. A safe handle implementation and any additive persistence requirements must be settled before coding.
3. Add bounded, first-party Admin connection reads and exact targeted disconnect, reusing OAuthGrantService locking/revocation checks. Return only safe grant summaries, account/client identities, actual scopes and validity/last-use metadata. Existing own-account endpoints keep their behavior; these additions do not automatically become MCP tools. Guard targets by issuer/native client/resource and current persisted Admin authority, with browser Origin/CSRF on writes.
4. Use existing CIMD preview/approve and manual client APIs, not a new approval engine. Bind any request shortcut to a live request plus verified metadata and expected revision so a stale request cannot broaden approval silently. Clearly report reapproval impact. Do not auto-approve requested Manage or automatically modify roles.
5. Compose the page from trusted Core summaries; do not implement authorization with browser-only joins. Apply existing lock ordering, transaction rechecks, bounded queries and response-generation/access-loss guards. Concurrent decline/continue, role edits, disconnect/refresh and block/sign-in require one consistent outcome. Audit existing native credential/session validity semantics before choosing the Connected DTO predicate.

## Implementation and acceptance after agreement

Create a dedicated feature worktree; record the final plan in PLAN.md before coding. Reusable read/decline/admin-disconnect/precondition behavior belongs in Core, HTTP/UI in app; no ns8-idp changes. Publish immutable Core only after exact-source local/package/native gates, then pin app dependency/lock and rerun consumer gates. Any required migration is additive and must preserve old identities, grants, blocks, history and settings.

Update README, AGENTS, administrator/user guides and interface documentation. Remove duplicate Admin membership editors from Account or replace them with a link to Workspace access, while preserving ordinary users' own connected-app controls.

Verify real disposable Reader, Editor and Admin browser workflows over native SSO/HTTPS: default Shared Reader; pending approval and decline; independent role elevation versus application approval and explicit consent; read-only token remains read-only after role/approval changes; independent manage-only scopes; exact per-grant disconnect with sibling/other-user positive controls; persistent block across repeated login and restart; explicit unblock without token resurrection; owner protection; Shared/protected-space boundaries; global client-disable distinction; pagination/stale responses/stale saves/CSRF; no jobs/schedules requests from access page; keyboard/accessibility and actual privacy artifacts. Run focused PostgreSQL/HTTP/UI checks then full packaging/JS/schema/shell/both native CI and actual report audits. Existing interactive Playwright and CPU-quota waivers remain unchanged. Supported dedicated-instance deployment/live acceptance follows reviewable exact CI images and preserves unrelated modules and the working connection candidate. No destructive recovery runs live.

## Implementation checkpoint — 24 October

Core0.33/schema0021 is published from immutable source
`ec2ac4f263a4736a6426c671a0353a4e764509f8`. Its exact
[full40082329366](https://github.com/Stell0/ns8-czero/actions/runs/40082329366)
and promotion verifier pass:1936 actual Python/PostgreSQL/packaging cases without
skips, Debian genuine upgrade21, Rocky installation26/three expected skips,
eight real browser workflows/privacy guards,28 numeric accessibility contexts,
three inspected OAuth-query artifacts with zero candidates and five actual
scan/SBOM pairs. [Publisher40086544147](https://github.com/Stell0/ns8-czero/actions/runs/40086544147)
completes successfully. Downloaded immutable
[core-v0.33.0 assets](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.33.0)
match checksums and every Core Python byte matches the verified source:
wheel SHA256 `61ccec3abce4216e663251d4502723c02b2819e9e919526e9735fc060bdf8777`,
archive `13759f5af182819e7b0bc1cc889f89df8e880ad48b57e8e1fa0330219b078c9d`.
Both supplied distributions install independently and expose the new service
outside the source tree, without application/NS8 dependencies. Do not replace
these artifacts. These native results precede the new application UI.

Retained earlier failures are resolved: c01f013 found one genuine schema0015
legacy account-list regression (1933 passes/one failure);999aada preserves that
old query and passes1934. Source d6cc0e3 corrects in-progress provider-check
status and passes1935 locally, but its native40079749606 has one asynchronous
protected-space UI synchronization failure; it is not accepted. The final app
waits for the exact selected space before its assertions. Core ec2ac4f also
preserves the existing configured-owner override when schema0019 left an old
block marker, without deleting data or changing grants. Its local whole run
has1935 passes/one five-second statement-timeout setup error under host load;
the affected24-case SDK group reruns successfully and the exact CI1936-case
whole matrix passes. Keep failed private evidence; never present failed runs
as whole-suite passes.

Application0.52 pins the released Core0.33 tag and immutable source in its lock.
It implements the approved table, browser-only access API and separate
Advanced/Protected spaces/Background work surfaces. Legacy mounts retain
first-party access controls without mounting or advertising OAuth/MCP. The
earlier draft whole matrix passes1936 without skips; later focused transport,
native and consumer checks pass, and current Node24 controllers pass178.
The final whole consumer matrix against the actual published wheel passes1959
without skips in651.65s; current controller checks pass178. Schema
compilation, individually parsed shell inputs and21 Robot dry runs pass; dry
runs are not native browser acceptance.

Final native tests freeze all three genuine installed PR33 source4d61cf2
images, app0.51/Core0.32/schema0020, in upgrade_predecessor.json and Robot.
They require exact existing background grant/token/code rows, successful
rotating refresh and a delegated profile read after upgrade, followed by
isolated client/provider cleanup. Artifact audits additionally require ten
independent measured access stages: actual approval and decline, one-connection
disconnect with sibling/other-user controls, persistent blocking across two
sign-ins and an observed native service restart, unblocking without old-token
revival, and Reader/Editor/Admin browser permission changes. The two new fixture
and audit dependencies are explicitly registered for managed consumer delivery.
This was the pre-acceptance checkpoint; final native and live results are recorded above.

Production MetadataFetcher fetches the fixed public JSON example through real
public DNS/TLS/MIME validation, digest
`8f2cafd1a4bfd3c7469bd0f9f59c0c5281c4c26464966ec36c7a43d161337d5b`.
Keep test-workspace-client-v1 at9fc9594 unchanged. No security-policy weakening
was introduced. This historical checkpoint preceded the accepted exact-source
CI, native, dedicated update/live and reviewed promotion results recorded above.

### Native findings and corrections

The first application full run
[40088486541](https://github.com/Stell0/ns8-czero/actions/runs/40088486541)
at71b3d96 is unaccepted: actual Debian genuine predecessor upgrade21 passes;
Rocky installation24 passes/two failures/three expected skips. All ten measured
people-access phases pass independent strict grading, including approval,
exact decline/disconnect, persistent block across renewed sign-in and an
observed service restart, unblock without old-token revival and all three
permission presets. Three actual XML/browser-log query artifacts contain zero
OAuth-query candidates. Passing those stages does not establish full acceptance.

The subsequent Advanced check fails because the new browser fixture leaves
discovery enabled before the original disabled-policy check. Source45f9163
restores the original boolean in finally on both success and failure. Two
forced-browser-stop regressions and39 existing focused cases pass; its complete
released-Core matrix passes1961 without skips in609.86s and21 Robot dry runs
pass. Its completed [full40091589934](https://github.com/Stell0/ns8-czero/actions/runs/40091589934)
remains failed: Debian21 passes, Rocky25 passes/one skip-target failure/three
expected skips, with three query artifacts containing zero candidates.

A separate protected-space failure is the actual numeric accessibility guard:
missing_skip_target=1. A subpage base URI plus space-link rewriting can send the
skip link to another document. The correction preserves the current document,
selected-space query and legacy prefix in shared navigation. The probe now
checks the resolved origin/path/query/fragment target instead of only the raw
fragment attribute. It rejects both another page and another space. Actual
native Tab/Enter/focus checks cover Advanced, Background work and Protected
spaces, preserving the existing ordinary-page keyboard check. Current Node24
checks pass185, focused Python43 and21 Robot dry runs pass; the complete
released-Core matrix passes1963 without skips in600.14s. Fresh
exact-source full/image/native acceptance followed at e384bed, as recorded
above. Neither older candidate was deployed or merged. Core0.33 artifacts remain
immutable; the accepted installation is now the corrected e384bed runtime.

## Settled implementation interfaces

Core 0.33 / schema0021 adds c0_accounts.access_revision (monotonic bigint) and a separate random UUID c0_client_onboarding.id. Neither is authority. AccessService keeps legacy set_role behavior; optional expected_revision rejects stale edits and skips unchanged UI saves. WorkspaceAccessService(grants) supplies first-party Admin summaries, bounded account pages (25, max100), per-person request/connection pages (10, max50), request-bound preview/approval and decline, and exact per-grant disconnect. All pages report has_more. Reads expose locally observed connection state only; stale provider verification is renewal_required, not a false assertion of successful access or permanent disconnection. No provider network call occurs in overview transactions. Existing application/client scope contracts remain unchanged.

Routes: GET /api/v1/access/workspace?offset=&limit=; GET /api/v1/access/accounts/{id}/applications?offset=&limit=; POST /api/v1/access/requests/{id}/preview; POST /api/v1/access/requests/{id}/approve; DELETE /api/v1/access/requests/{id}; DELETE /api/v1/access/connections/{id}. Existing PUT account role gains optional expected_revision. The request approval reuses CimdService's same transaction implementation, verifies the still-live request and account after I/O, preserves existing approved scopes and rejects disabled clients. Approval of a blocked account fails. No new MCP tool or discovery default is added.

UI routes: /admin (access), /admin/advanced (technical client controls), /admin/spaces, /admin/work (jobs/schedules). Preserve existing manual client and space/task controllers on their separate surfaces. Account links to Workspace access instead of duplicating role edits; self-service connection controls remain unchanged. App adoption follows verified immutable Core publication, not an unreviewed dependency replacement. PR33 was kept frozen and merged first; PR34 then passed its own current-head gates and merged.


---

## Earlier roadmap checkpoint

The sections below retain the earlier plan and observations. Their pending/current
installation statements are historical; the accepted-runtime section above is
authoritative for PR33/PR34 and the installed predecessor. Other M21 release gates
remain open as explicitly stated.

## Operator priority — persistent OAuth connections (23 October 2026)

The operator authorizes unattended ChatGPT maintenance connections after reviewing token lifetime and revocation tradeoffs. Keep five-minute access tokens and rotating refresh credentials; new explicitly consented background connections have a thirty-day inactivity deadline and no fixed maximum lifetime. Normal browser sessions retain their current bounds. Existing grants are never silently upgraded. Scheduling or running knowledge maintenance is outside this implementation; actual multi-day ChatGPT scheduling remains acceptance work.

**Entry and preservation:** PR32 is merged as `d4a97349e8e7aa83789b82a78eccbc075c754e84`, with the tested/deployed `fa64f3d390a9514d751c33e5ab4a5a941193ab78` tree. Its [main39933530291](https://github.com/Stell0/ns8-czero/actions/runs/39933530291), publication, actual downloaded native/privacy/scan artifacts and full promotion verifier are completed/successful. Sourcefa64 full39777449607 and independently downloaded native/privacy/scan artifacts pass: Debian upgrade21, Rocky installation26/three expected skips, eight browsers/privacy guards,25 accessibility contexts and zero query candidates. The supported dedicated update/restart and original data/settings/schedules/nine-unrelated-instances/root-journal checks pass. Real connection/read succeeds by operator report; packaged-skill use and seven quota-blocked model cases remain incomplete. Preserve PR32, all prior worktrees and the installed candidate images; do not substitute documentation images or claim M21 release acceptance.

Frozen installed predecessor: `fa64f3d390a9514d751c33e5ab4a5a941193ab78`, canonical tag `ci-fa64f3d390a9514d751c33e5ab4a5a941193ab78-39777449607-1`, app0.50.0/Core0.31.1/schema0019.

| Image | Installed digest |
| --- | --- |
| module | `sha256:acdd8f9b06b3cb0fd9ce8f45367ddf4aba26bf6a5a7f51d423b0e904642604c5` |
| app | `sha256:0273abd79473dadc2b106f5d4d32e0471c29729c78c6f4d3d6c4763a1b818ed1` |
| postgres | `sha256:80d8f51e603f6ba59d300d94a3d9b2e725f3a3f699c44bd4981170c58ead4bf2` |

**Verified provider prerequisite:** A private real-HTTPS probe using only the existing dedicated C0 client obtained `offline_access`, verified the same identity, refreshed successfully after logging out its own provider session, revoked its offline credentials and required refresh rejection. No provider configuration, account role, application content or client registration changed. No ns8-idp or NS8 platform Core change is currently required. Keep raw authorization data and evidence outside Git.

**Settled implementation:**

- Core0.32/schema0020 introduces an opt-in background-connection policy and explicit persisted authority kind. Interactive authority remains bounded; background authority requires provider-attested offline credentials, current roles and thirty-day inactivity. Browser cookies remain bounded even when they reference offline authority. New background consent requires same-origin CSRF, a valid pending OAuth request and fresh same-account native SSO; login purpose/expected identity are bound to one-use persisted login state.
- Persistent grants have explicit kind, activity/idle deadline and revocation semantics, independent of the browser expiry. Bind the same issuer, native client, approved client revision, exact resource and actual consented scopes. Keep current membership/space checks inside operations. Browser logout retains explicitly approved background grants; per-connection disconnect, client/account revocation and provider rejection deny subsequent use. Provider outages confer no new authority and retain retryable credentials only after a definite retryable outcome.
- Persistent refresh credentials remain opaque 43-character values. A domain-separated keyed family/generation authenticator permits issued-old-token replay detection with bounded storage, replacing the finite rotation-history cap only for new persistent grants. Preserve legacy tokens and loaders; authenticate replay before SDK scope validation, commit family revocation, serialize rotations and reject fabricated/future/wrong-client credentials without revoking another family. Refresh never adds scopes. Code/state/consent and access-token expiry stay short.
- Add migration fields without changing old grant/session lifetimes. New Core DTO/SDK adapters handle persistent authority while access-token expiry remains finite. Restores/native client or secret replacement must reject old authority. Native settings expose the optional background policy; application consent and account connection controls explain lifetime, last use and disconnect. Plain readers fetch no Admin lists.
- Reusable provider/authority/grant behavior belongs in Core; HTTP, cookies and UI in the app; NS8 settings and lifecycle in numbered scripts. Publish immutable verified Core artifacts before final released-consumer adoption. The feature starts on an isolated branch, preserving the merged onboarding source and all unfinished work.

**Validation and acceptance:** focused PostgreSQL migration, same-account offline login, current-role/revocation, expiry/idle extension, rotation/replay/concurrency, wrong binding, provider outage/recovery, browser logout versus disconnect, bounded history and old-client regressions; then full Python/PostgreSQL/packaging, JavaScript, schema/shell/Robot and exact-source producer/released-Core/both-native artifact gates. Use frozen deployedfa64 image identities for genuine upgrades. Only after those pass perform a supported C0-only checked backup/update, readiness, original knowledge/files/settings/clients/schedules/unrelated inventory, restart and bounded positive-control journal audit. Actual ChatGPT consent/write/readback and consecutive nightly runs beyond24hours without fresh login are required; revocation must stop the next run. No model quota bypass, new schedule, stable release or unrelated IdP change is authorized. Existing waivers remain unchanged.

**Verified Core publication:** Source `22d813409b820958845b8b7b7493284a3012c92a` passes 1862 actual local Python/PostgreSQL/packaging cases without skips and [full 39964867651](https://github.com/Stell0/ns8-czero/actions/runs/39964867651). Independently downloaded reports verify Debian genuine predecessor upgrade 21, Rocky installation 26/three expected skips, eight browsers/privacy guards, 25 accessibility contexts, three OAuth-query artifacts with zero candidates and five actual scan/SBOM pairs. The full promotion verifier passes. [Core publication 39972262492](https://github.com/Stell0/ns8-czero/actions/runs/39972262492) completes successfully at that exact source; downloaded `core-v0.32.0` assets match SHA256SUMS: wheel `eb48289106d987ad2672fd93da3407ab566be972ba8ebfaf09611252c723f6a1`, archive `79cba3df87877f543a6939faa7e57cd17eb5684a1be0379a6204a67bfcfd6bfe`. Both contain schema 0020. This publication does not establish application or live acceptance.

The genuine 0019 migration preserves original columns, ciphertext and bounded grants. Controlled-clock PostgreSQL cases exercise a year of daily use, 2050 rotations with two current token rows, separate browser idle/absolute bounds, provider outage/recovery and replay revocation. The old source fails both access-activity/refresh-deadline boundary controls; the correction extends only the current unconsumed refresh credential with authenticated activity. No absolute connection lifetime is imposed on explicit background grants.

**Retained failures and corrections:** Core 2668b2d/full 39952548426 fails Debian predecessor setup because the profile fixture expected closed admission although frozen fa64 admits verified Readers; later failures cascade and CI cancels Rocky. The corrected 4e75484/full 39958341465 completes successfully with audited native artifacts but is superseded by the refresh-deadline correction above. Its interrupted local rerun is not counted as a pass. A failed local run caused by temporary-directory quota is retained privately; rerunning the final frozen source with an isolated workspace temporary directory yields the 1862-pass result. No agent cancellation or failed-candidate deployment occurred.

**Application adoption:** Application 0.51.0 pins the published `core-v0.32.0` source and lock, with compatible range >=0.32.0,<0.33.0. Explicit optional background consent binds one-use same-account offline login; a verified active offline session may be reused before final explicit approval. First-party Account controls list only the user's connections and disconnect with same-origin CSRF. NS8 settings expose whole-day inactivity of 1–365 days, default 30, for new connections, preserve it through update/restore and leave browser policy unchanged. Native disposable acceptance now requires measured 120-second browser expiry with subsequent background refresh, actual read/write SDK, replay/disconnect/provider revocation, and persistent grant/policy recovery across update and clean restore. Those new native checks are pending; the Core bridge native run did not exercise the new application. The initial adoption run passes 1907 cases and fails only three version-consistency assertions: the runtime constant still reported0.50 while package metadata reported0.51. The constant is corrected and all120 application cases pass; a clean full rerun of the frozen final candidate is required. Focused app checks pass 691, additional native-helper/HTTP checks 162, UI 165 and immutable administration build; final full released-consumer/image/both-native validation is required before deployment. The dedicated installation remains unchanged.

**Application policy correction:** Frozen `bc59aabb7662af1c7fa82d4a6cd5db6df3666fc5` passes all1910 local Python/PostgreSQL/packaging cases without skips and is submitted as PR33/full39976845841. Its image, released-Core, runtime, versioning, scans and CI local checks pass while native runs continue. Subsequent review reproduces four failures: new consent could reuse an older offline sign-in after the administrator shortened or lengthened the new-connection inactivity setting. This candidate is not authorized for deployment even if its earlier acceptance suite completes successfully; keep its evidence and let the frozen run finish.

The application now reuses offline sign-in only when its saved limit matches the current setting, and rejects direct consent under a mismatched limit. Fresh same-account sign-in applies the new setting; existing grants keep their snapshots and continue renewing. Focused signed-provider HTTP checks pass26 cases, including all four corrected negative controls. Native acceptance additionally changes the actual setting, rejects old-policy consent, completes fresh offline sign-in, renews both old/new grants and restores settings while revoking owned credentials. This is application configuration/consent selection; Core0.32/schema0020 and its published package bytes remain unchanged. Fresh full local/image/both-native acceptance is required for the correction before any live update.

The completed first application run39976845841 fails actual Debian20 passes/one failure and Rocky24 passes/three expected skips/two failures. Both fail the exact knowledge change observer after the new recovery SDK made successful content mutations between frozen checkpoints. Rocky then observes the temporary seven-day setting because restore verification stopped before cleanup; its consent-help check correctly rejects that state. The standalone measured background browser/logout/refresh/read-write/replay/disconnect proof and recovery seed/update execute, but clean-restore acceptance is incomplete. Downloaded failed XML/browser logs are retained privately; all three actual query artifacts have zero OAuth-query candidates, including refresh tokens. The installation is unchanged.

The correction retains the exact observer. Recovery SDK checks both protocol modes, verifies reads and requires an authorized stale-revision write to return a conflict rather than a scope denial, comparing the complete bounded knowledge history and retained page before/after. Successful write/readback/archive remains mandatory in the separate standalone probe. Focused actual SDK positive/read-only negative controls pass; the complete correction selection passes146 PostgreSQL/HTTP/native-wrapper cases. The private operational helper also passes four signed HTTP/SQL checks, including the exact native policy-change helper; these controlled tests do not establish installed provider acceptance. Artifact/browser guards now also reject refresh-token query diagnostics. Fresh full exact-source local and CI/native runs remain required.

Corrected source `2adc9a91d2c3739c3a16616846f232c8abbe9abb` passes1919 local Python/PostgreSQL/packaging cases without skips,165 JavaScript cases, schema/shell checks,21 Robot dry-run cases and independent released-Core installation/source verification. Full39988063836 passes local/image/runtime/released-Core/scan jobs and actual Debian upgrade21, including new-policy consent and unchanged knowledge history across update/restore. Rocky reaches the shared runner's sixty-minute job limit after slow environment setup; its report is truncated before all browser workflows complete. This cancelled run is incomplete acceptance, never a deployment authorization. Keep its downloaded diagnostics privately. The supported shared-workflow timeout input is now ninety minutes for each native distribution; retain all suite assertions, application bounds and existing waivers, and require fresh exact-source full acceptance.

Source24d0d6c/full39997306298 passes1919 CI Python/PostgreSQL/packaging cases and actual Debian21. Rocky completes25 passes/three expected skips with one OAuth-browser failure. Admin consent, background access and Account disconnect pass, but the next Reader case requests the identical client descriptor after Admin cleanup disabled it. Registration correctly returns the disabled idempotent result and authorization correctly fails. The new signed HTTP/PostgreSQL regression reproduces that exact cleanup/reuse failure. Each disposable browser case now uses a distinct hostile-text client name, retains explicit cleanup, and verifies that earlier disabled clients stay disabled. Product/Core behavior is unchanged. Preserve the failed reports; require fresh exact-source full/native acceptance before deployment.

Source233f64d/full40005084606 passes1920 CI Python/PostgreSQL/packaging cases, Debian21 and all eight actual Rocky browser workflows, including Admin/Reader/Editor consent and Account disconnect. Rocky's combined native SSO case reaches its20-minute aggregate timeout during the required second protocol pass: provisioning takes159 seconds, the first complete SSO/renewal/offline/background sequence792 seconds, and the repeat is interrupted after226 seconds. All first-pass measurements are valid, including338-second renewal and179-second background/browser-expiry checks. The suite wrapper's successful shell step is not the Robot verdict; the completed native job/report fails and this candidate is not deployable. The SSO aggregate budget becomes30 minutes, retaining every assertion, repeat, individual SSH/probe deadline and application lifetime. Fresh exact-source full/native gates remain required.

The local source233f64d matrix covers1914 main Python/PostgreSQL cases and six fresh packaging cases without skips. Two whole runs retain artifact-install setup errors caused by slow dependency downloads (1918 passes/two errors and1916 passes/four errors); a checksum-verified public dependency wheelhouse, excluding Core itself, lets all six unchanged packaging/rebuild/install/migration checks pass offline in14.73 seconds. Core is still built from the frozen checkout. These are a combined local matrix, not a single clean whole local invocation; actual CI completes all1920 in one run. Preserve failures and private evidence, and keep the installation unchanged until the final candidate passes.

## Current checkpoint

23 October 2026: PR32 self-service onboarding is merged as `d4a9734` and its actual main CI/publication and downloaded native/privacy/scan artifacts pass. The dedicated instance runs tested `fa64f3d`, app0.50.0/Core0.31.1/schema0019, after the supported update and preservation/restart/journal gates. The operator confirms actual ChatGPT connection/read. Persistent OAuth development is the current authorized priority above; actual packaged-skill use and remaining model cases stay incomplete.

Historical M00–M20, Agent Memory AM0–AM6, failures, observations, measured limits and exact CI/source identities are retained in the [archived plan](docs/history/PLAN.md). Historical status statements do not reopen accepted work. The original root checkout's dirty documents and recovered M20 worktrees remain untouched.

## Current installed runtime

Source `fa64f3d390a9514d751c33e5ab4a5a941193ab78`, canonical tag `ci-fa64f3d390a9514d751c33e5ab4a5a941193ab78-39777449607-1`, app0.50.0/Core0.31.1/schema0019. The priority section above freezes all three installed digests. Do not replace these images with documentation/main-marker builds. Earlier self-service and clean-start checkpoints below are historical; the accepted M19 source and immutable Core0.31.0 artifacts remain in the [historical evidence](docs/history/PLAN.md#m19-deployed-acceptance-and-main-closeout--21-october-2026).

## Delivery loop

Follow [CI policy](docs/ci-policy.md) and [development guidance](docs/development.md). Settle decisions, implement one milestone, run local disposable tests, open a reviewed PR, require full exact-source runtime/image/both-native/audited artifacts, deploy only to the authorized dedicated C0 instance through supported native actions, complete live acceptance, regularly merge and verify actual main publication. Record final evidence on a separate closeout branch. Documentation-only closeouts use their explicit light checks and preserve runtime images.

The existing interactive Playwright and CPU-quota waivers remain. No stable NS8 module release is claimed. Vendor findings, real-provider quality and deployment-specific IdP/proxy/log policy are distinct maintenance/release work.

## M21 — Documentation and skills release readiness

**Authorization and entry:** The operator approves the settled plan, including
repository plus Use with AI cleanup, per-instance end-user plugin bundles, actual
packaged skills on ChatGPT web, individual/private and managed-workspace routes,
and ready artifacts/guides without public-directory submission or module tagging.
Use the verified M19 completion marker; preserve the accepted38a8654 installation,
all original drafts and waivers. Windmill remains separate.

**Implementation decisions:** Keep README a short product/quickstart entry;
separate user/operator/contributor guides. Keep AGENTS current and PLAN focused
on status/roadmap; archive historical evidence with repaired links/compatibility
anchors and sanitized deployment details. Preserve public source/CI references.
Update the five existing developer skills and required upstream-managed references.
Align installed Use with AI with staged Admin/user CIMD onboarding and current
session/role/space/citation/upload/retry behavior. Core/schema/OAuth remain intact;
installed presentation changes use an app patch version and unchanged dependencies.

Package three instruction skills: setup, cited research and explicit knowledge
maintenance. An offline generator accepts the operator's canonical HTTPS MCP URL,
registered ChatGPT app ID, plugin name and output location; emits a deterministic
versioned directory/ZIP/checksums/marketplace; rejects unsafe inputs/existing
outputs and never publishes or collects credentials. Web packages reference the
existing app via `.app.json`, without inline MCP server declarations that make
GitHub-imported plugins Desktop only. Prove private Plugin Creator setup from the
packaged files plus correct app binding and managed GitHub marketplace import.
Required workspace/account features are explicit prerequisites; absence is an
incomplete gate, never a desktop/SDK substitution or release-ready claim.

**Acceptance:** Validate maintained file/anchor links, safe examples/current facts,
all skill metadata/references/license/manifests, deterministic archives and two
instance bindings. Exercise documented commands in disposable environments and
independent actual MCP/database skill scenarios: cited reads, ambiguity/denial,
untrusted retrieved instructions, sanitized ingestion, conflicts/uncertain retries
and read-back. Require a cold-start tester using only guides/package. Actual
ChatGPT web must prove packaged skill activation/app/account/citations, authorized
controlled edit, Reader denial, renewal/reconnect/revocation on both supported
routes. Run full exact-source/released-Core/image/both-native/artifact checks for
the installed-guide change, all8 browsers and the usual reviewed deployment,
regular merge/main publication/separate closeout loop. Explicitly reviewed doc
paths may use lightweight checks; executable plugin packaging inputs cannot.
No stable release, public listing or workspace-wide rollout is claimed by M21.


### Implementation checklist

- [x] Verify reviewed M19 closeout main marker; base M21 on it without losing drafts.
- [x] Reorganize root/user/admin/developer/reference docs, archive evidence and preserve old anchors.
- [x] Maintain five developer skills and explicitly registered reusable references.
- [x] Implement three end-user skills and deterministic per-instance web package generation.
- [x] Align installed guide at app0.49.1 with Core0.31.0/schema0018 unchanged.
- [ ] Pass meaningful package/link/schema/skill checks, cold-start and independent model/MCP/database scenarios.
- [ ] Pass exact local, released-Core, images, both native distributions and actual artifact audits.
- [ ] Prove both actual ChatGPT web installation routes and their account/space/read/write/denial/session/revocation acceptance.
- [ ] Complete C0-only deployment preservation/journal gates, human review, regular merge and main publication.
- [ ] Complete separate checked documentation closeout; freeze accepted runtime as next predecessor.

See [release-readiness evidence](docs/release-readiness.md). Incomplete web or operator prerequisites are recorded as pending, never inferred from a generated package.

## Later phases

Windmill integration follows separately after M21 acceptance. Public plugin-directory submission, stable module release and workspace-wide rollout each require their own scope and acceptance; this phase does not perform them.

### M21 implementation checkpoint — 21 October 2026

The guides, historical archives/legacy anchors, five developer skills and managed fork reference, three end-user skills, offline per-instance packager and installed Use with AI update are implemented. App0.49.1 changes presentation only; Core0.31.0/schema0018 and all dependency bytes remain unchanged. Native genuine-upgrade inputs freeze the accepted M19 trio. Plugin inputs remain full-validation material; only the explicit reviewed Git-only guidance paths receive the docs exemption.

The full local development suite passes1733 actual Python/PostgreSQL/packaging cases with no skips; later focused changes pass163 cases. Controller140, all8 skill metadata validators, the published portable manifest schema,217 local documentation/anchor links, Go schema compilation, individually parsed shell inputs and21 Robot dry runs pass. The shell-parser check now rejects a deliberate syntax error in a later file; the earlier multi-argument command checked only its first file. The app lock validates without dependency changes. These are local development results; exact-source full CI/native/artifacts remain pending.

An independent cold-start reviewer validates the offline package/checksums/references and finds three concrete documentation gaps. The added operator candidate record, empty-instance first-content walkthrough and explicit Creator skill/reference-preservation check resolve all three on reinspection. This is a read-only documentation evaluation, not actual new installation or web acceptance. A private instance-bound package is prepared outside Git. No browser surface is available to the agent; actual Plugin Creator/managed-import feature availability and account observations remain pending. Independent model/MCP/database instruction measurements are prepared separately and cannot establish automatic skill activation or ChatGPT web installation.

Original checkout/recovered M20 heads and dirty status match the preserved baseline. No live runtime update, stable tag, directory submission or workspace-wide rollout has occurred.

### M21 real-web feedback and correction — 22 October 2026

Frozen `c630cb6` passes [full CI39646163590](https://github.com/Stell0/ns8-czero/actions/runs/39646163590):1740 actual Python/PostgreSQL/packaging cases, producer/released-Core/images, Debian genuine M19 upgrade21 and Rocky installation26/three expected skips/all8 browsers. Independent actual artifacts pass25 accessibility contexts,8 privacy guards,3 query-audited artifacts with zero candidates and5 scan/SBOM pairs. Exact promotion passes. An initial independent audit invocation lacks its repository-relative predecessor fixture; the retained downloaded reports pass the corrected read-only audit from the exact checkout.

Both pinned model arms pass14/14 scenarios with46 actual MCP calls each and independent database/trace plus final-prose grading. Packaged/guidance-only measured runner totals are461.47/478.05s and1,402,707/1,337,136 tokens: single samples, not a performance or quality-improvement claim. A separate synthetic selected-text task confirms an unselected credential canary is absent from all resulting database state. Failed wrong-driver and nested-sandbox attempts remain private and are not quality scores.

Actual operator web testing rejects the first marketplace-shaped ZIP with `Expected a single plugin archive`. The generator now puts one plugin's manifest/app reference/skills at ZIP root, while the directory retains the GitHub marketplace. Regression/determinism/binding/link checks pass44 cases; all9 plugin payload files remain byte-identical to the measured package. A replacement archive is delivered privately; actual upload acceptance and the other web gates remain pending. This correction requires fresh full CI; c630cb6 is not deployed or merged.

The operator separately reports reconnect requesting unapproved `c0:admin`. Read-only inspection confirms the existing client is enabled and approved only for `c0:read`; no scopes have been expanded. Intended research/editing versus administration is pending operator direction. Supported dedicated backup and actual restic read-data check pass with all existing backup plans restored;8 original HTTP views and3 schedules are captured. Deployment is held for corrected candidate acceptance and preservation baselines will be refreshed before update.

## M21 follow-up — Simple self-service ChatGPT onboarding

**Operator direction (22 October):** Simplify `/agents` for nontechnical users: direct personal-Plugins link, suggested C0 name/description/canonical MCP connection with small accessible copy icons, generated instance-specific `.skill` and plugin ZIP downloads, visible client/user permission management, reliable first OAuth sign-in and default Shared read admission for authenticated users. This supersedes M21's earlier presentation-only/Core-unchanged and offline-only packaging limits. Preserve all unfinished work and deployment waivers.

**Verified entry:** PR31 merges as `0040c8930257e0a605e4768ef76dab84490f8691`; its completed main39745026479 and independently inspected native/privacy/scan artifacts pass. Tested/deployed candidate `37301886c4e28a5982c85cd837a113a96a54d2e0` has the same tree. The operator explicitly requests and approves supported removal/recreation for a fully clean start after a supported backup/actual restic read-data check. The new dedicated instance runs app0.49.1/Core0.31.0/schema0018 with restored configuration, one empty Shared space, owner only, zero old clients/content/history/files and three built-in schedules. All eleven unrelated module identities are preserved. The removed native client is absent. Actual fresh ChatGPT acceptance remains pending; no M21 completion is claimed. Deployed images remain frozen at:

| Image | Current installed digest |
| --- | --- |
| Module | `sha256:b7177aaed0d61b5ce9913173b25d57fbe150457155619d7f0429afefbc36815e` |
| App | `sha256:fcd6c9a1552774e065a4ab04ed1f19a9244c708bee9ec4c9407249d1f509ea72` |
| PostgreSQL | `sha256:7aefea399df70ed31ed294358a768c47c40c58870224828063a765a7ecb5bf53` |

Canonical tag: `ci-37301886c4e28a5982c85cd837a113a96a54d2e0-39737449917-1`. Preserve it as the genuine next upgrade predecessor; documentation/main images do not replace it.

**Settled interfaces and responsibilities:**

- Core0.31.1 adds opt-in new-account Reader admission, persisted explicit account blocking and a bounded browser-bound pending-client authorization service. Schema0019 is additive. Existing Core callers retain closed admission by default. Migration marks existing unadmitted identities blocked, preserving earlier revocations; existing memberships/owners/grants are unchanged. Trusted verified identities alone can receive admission; role/scopes/space grants remain authoritative. Membership removal records a persistent block and revokes existing authority, including after repeated/concurrent sign-in.
- Pending client authorization stores a validated authorization request for five minutes behind separate opaque request/browser hashes, current issuer/native-client/resource and bounded counts. It performs no network work and grants no authority. Only signed-in users can register an approval request; Admins see bounded pending metadata URLs/callbacks/scopes, never state/PKCE/native secrets. Continuing requires same-origin CSRF, a current verified session, fresh approved client metadata, exact callback/scope validation and one-use transition into existing consent. Expired, disabled, changed, blocked and replayed requests fail closed. Existing UUID clients and approved-client flows retain their validation. Malformed/duplicate/resource/credential requests remain strict errors; valid unapproved CIMD requests get the human flow only while discovery is enabled.
- The application opts into Reader admission, returns pending onboarding across normal SSO without placing OAuth parameters in redirect URLs, and presents clear approval/continue steps. C0 Administration exposes Users first, then pending ChatGPT connections and reviewed-client controls; no automatic broad client approval or Admin scope is introduced.
- `/agents` derives name/description/hostname/MCP URL from trusted configured instance metadata. Three compact icon controls retain keyboard labels, copy feedback/manual fallback and stale-response guards. Technical details move to disclosures. A `.skill` ZIP contains one instance-bound memory workflow and declared MCP dependency; it contains no credential. A web plugin ZIP references the user's existing registered ChatGPT app; the UI accepts its technical ID/management URL and explains where to copy it. It does not invent a binding, add inline MCP that makes workspace imports Desktop only, or claim installation grants access.
- Reuse one application packaging library from offline and HTTP paths. Serve in-memory deterministic bounded archives with explicit filenames/no-store/no-sniff and no remote fetches or writes. Runtime includes only explicitly allowlisted end-user package assets and GPL license; repository development skills/tests/plans stay excluded. Update runtime audits accordingly.
- Native lifecycle remains numbered scripts. No host logging, shared identity-provider user, unrelated application, CPU-quota or stable-release change is part of this work.

**Delivery:** First validate/publish immutable compatible Core artifacts from exact successful local/both-native source, then pin the application dependency/lock and complete final consumer/image/both-native checks. Use focused commits on an isolated branch, reviewed PR, supported dedicated-instance deployment and actual ChatGPT acceptance before final closeout. Runtime behavior does not deploy from local tests alone.

**Acceptance checklist:**

- [ ] Core database cases: first/concurrent verified admission, wrong/expired issuer identity, unchanged existing roles, persistent block/regrant/revocation, protected-space isolation; genuine schema0018 migration/repeat/restore and package distribution.
- [ ] Pending-client cases: duplicate/malformed/oversized requests, policy-off/no unauthenticated fetch, cookie/issuer/native/resource bindings, limits/expiry, signed-in queue privacy, Admin-only preview/approval, role-loss/provider failure, one winner/replay, exact callback/PKCE/scopes and unchanged existing clients.
- [ ] Downloads: two configured instances, deterministic bytes, safe names/app IDs/URLs, no secrets/unrelated assets, valid skill/plugin manifests/references/dependencies, installed-image downloads and package license.
- [ ] UI: simple signed-out/signed-in states; direct links and suggested text; icon clipboard success/failure/keyboard/accessibility; stale replies/access loss; visible Users/connection approval and Reader/Editor/Admin/blocked behavior in actual native browsers.
- [ ] Focused plus full Python/PostgreSQL/packaging, JavaScript, schema/shell/Robot and both-native/actual artifact audits; immutable Core release and final released consumer checks.
- [ ] C0-only backup/update/readiness/data/client/schedule/inventory/restart/journal acceptance; actual fresh ChatGPT OAuth, `.skill` import, plugin import, cited read/repeat and permitted editing/denial. Keep actual web observations distinct from model/SDK checks.
- [ ] Reviewed regular main promotion, completed main/publication and separate checked evidence closeout; freeze final accepted runtime.

<details>
<summary>Historical section links</summary>

These anchors preserve links to the retained historical record.

<a id="c0-implementation-plan--milestone-by-milestone-codex-handoff"></a>[C0 implementation plan — milestone-by-milestone Codex handoff](docs/history/PLAN.md#c0-implementation-plan--milestone-by-milestone-codex-handoff)

<a id="product-contract-do-not-quietly-change"></a>[Product contract (do not quietly change)](docs/history/PLAN.md#product-contract-do-not-quietly-change)

<a id="source-precedence-and-selection"></a>[Source precedence and selection](docs/history/PLAN.md#source-precedence-and-selection)

<a id="non-negotiable-execution-loop-for-every-milestone"></a>[Non-negotiable execution loop for EVERY milestone](docs/history/PLAN.md#non-negotiable-execution-loop-for-every-milestone)

<a id="tests-and-ci-conventions"></a>[Tests and CI conventions](docs/history/PLAN.md#tests-and-ci-conventions)

<a id="milestones"></a>[Milestones](docs/history/PLAN.md#milestones)

<a id="m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x"></a>[M00 — Rebrand kickstart, create working CI and smoke-test the module [x]](docs/history/PLAN.md#m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x)

<a id="m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x"></a>[M01 — Minimal Python runtime, Web UI and Core/application separation [x]](docs/history/PLAN.md#m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x)

<a id="m02--ns8-configuration-traefik-and-administrator-ui-x"></a>[M02 — NS8 configuration, Traefik and administrator UI [x]](docs/history/PLAN.md#m02--ns8-configuration-traefik-and-administrator-ui-x)

<a id="m03--dedicated-postgresql--pgvector-and-migrations-x"></a>[M03 — Dedicated PostgreSQL + pgvector and migrations [x]](docs/history/PLAN.md#m03--dedicated-postgresql--pgvector-and-migrations-x)

<a id="m04--backup-restore-and-upgrade-safe-persistence-x"></a>[M04 — Backup, restore and upgrade-safe persistence [x]](docs/history/PLAN.md#m04--backup-restore-and-upgrade-safe-persistence-x)

<a id="m05--ns8-idp-login-and-minimal-application-wide-authorization-x"></a>[M05 — ns8-idp login and minimal application-wide authorization [x]](docs/history/PLAN.md#m05--ns8-idp-login-and-minimal-application-wide-authorization-x)

<a id="m06--deterministic-jobs-and-database-backed-scheduler-x"></a>[M06 — Deterministic jobs and database-backed scheduler [x]](docs/history/PLAN.md#m06--deterministic-jobs-and-database-backed-scheduler-x)

<a id="m07--generic-application-object-model-and-reusable-crud-x"></a>[M07 — Generic application object model and reusable CRUD [x]](docs/history/PLAN.md#m07--generic-application-object-model-and-reusable-crud-x)

<a id="m08--source-ingestion-text-extraction-and-chunk-storage-x"></a>[M08 — Source ingestion, text extraction and chunk storage [x]](docs/history/PLAN.md#m08--source-ingestion-text-extraction-and-chunk-storage-x)

<a id="m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x"></a>[M09 — Versioned Wiki, entities, claims, provenance and PostgreSQL graph [x]](docs/history/PLAN.md#m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x)

<a id="m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x"></a>[M10 — Full-text, vectors, external embeddings and Jev/Kev System One RAG [x]](docs/history/PLAN.md#m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x)

<a id="m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x"></a>[M11 — REST/MCP parity, OAuth interoperability and `/agents` discovery [x]](docs/history/PLAN.md#m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x)

<a id="m12--full-c0-user-ui-and-ns8-configuration-experience-x"></a>[M12 — Full C0 user UI and NS8 configuration experience [x]](docs/history/PLAN.md#m12--full-c0-user-ui-and-ns8-configuration-experience-x)

<a id="m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x"></a>[M13 — Fork upgrades, C0 Core distribution and upstream contribution skills [x]](docs/history/PLAN.md#m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x)

<a id="m14--end-to-end-hardening-compatibility-and-release-gate-x"></a>[M14 — End-to-end hardening, compatibility and release gate [x]](docs/history/PLAN.md#m14--end-to-end-hardening-compatibility-and-release-gate-x)

<a id="after-m14"></a>[After M14](docs/history/PLAN.md#after-m14)

<a id="current-next-action"></a>[Current next action](docs/history/PLAN.md#current-next-action)

<a id="m15--reader-first-knowledge-website-x"></a>[M15 — Reader-first knowledge website [x]](docs/history/PLAN.md#m15--reader-first-knowledge-website-x)

<a id="chatgpt-mcp-integration--operator-plan-15-october-2026"></a>[ChatGPT MCP integration — operator plan (15 October 2026)](docs/history/PLAN.md#chatgpt-mcp-integration--operator-plan-15-october-2026)

<a id="integration-m15--oauth-authorization-parameter-compatibility-x"></a>[Integration M15 — OAuth authorization parameter compatibility [x]](docs/history/PLAN.md#integration-m15--oauth-authorization-parameter-compatibility-x)

<a id="integration-m16--mcp-authentication-metadata-and-permission-upgrades-x"></a>[Integration M16 — MCP authentication metadata and permission upgrades [x]](docs/history/PLAN.md#integration-m16--mcp-authentication-metadata-and-permission-upgrades-x)

<a id="integration-m20--renewable-browser-and-delegated-sessions--"></a>[Integration M20 — Renewable browser and delegated sessions [ ]](docs/history/PLAN.md#integration-m20--renewable-browser-and-delegated-sessions--)

<a id="m20-main-recovery-fixture-correction--20-october-2026"></a>[M20 main recovery-fixture correction — 20 October 2026](docs/history/PLAN.md#m20-main-recovery-fixture-correction--20-october-2026)

<a id="m20-corrected-runtime-closeout--20-october-2026"></a>[M20 corrected runtime closeout — 20 October 2026](docs/history/PLAN.md#m20-corrected-runtime-closeout--20-october-2026)

<a id="integration-m17--profile-identity-closed"></a>[Integration M17 — Profile identity (closed)](docs/history/PLAN.md#integration-m17--profile-identity-closed)

<a id="m17-deployed-acceptance-and-closeout--20-october-2026"></a>[M17 deployed acceptance and closeout — 20 October 2026](docs/history/PLAN.md#m17-deployed-acceptance-and-closeout--20-october-2026)

<a id="integration-m18--tool-guidance-accepted-and-closed"></a>[Integration M18 — Tool guidance (accepted and closed)](docs/history/PLAN.md#integration-m18--tool-guidance-accepted-and-closed)

<a id="m18-executed-evidence-and-closeout--20-october-2026"></a>[M18 executed evidence and closeout — 20 October 2026](docs/history/PLAN.md#m18-executed-evidence-and-closeout--20-october-2026)

<a id="integration-sequence-after-m20"></a>[Integration sequence after M20](docs/history/PLAN.md#integration-sequence-after-m20)

<a id="structured-object-creation-repair--active-operator-task"></a>[Structured object creation repair — active operator task](docs/history/PLAN.md#structured-object-creation-repair--active-operator-task)

<a id="m1--root-cause-and-regression-reproduction-x"></a>[M1 — Root cause and regression reproduction [x]](docs/history/PLAN.md#m1--root-cause-and-regression-reproduction-x)

<a id="m2--minimal-implementation-fix-x"></a>[M2 — Minimal implementation fix [x]](docs/history/PLAN.md#m2--minimal-implementation-fix-x)

<a id="m3--complete-validated-crud-regression-x"></a>[M3 — Complete validated CRUD regression [x]](docs/history/PLAN.md#m3--complete-validated-crud-regression-x)

<a id="c0-agent-memory--additional-operator-track"></a>[C0 Agent Memory — additional operator track](docs/history/PLAN.md#c0-agent-memory--additional-operator-track)

<a id="c0-am0--baseline-and-compatibility-contracts-x"></a>[C0-AM0 — Baseline and compatibility contracts [x]](docs/history/PLAN.md#c0-am0--baseline-and-compatibility-contracts-x)

<a id="c0-am1--mcp-native-text-evidence-ingestion-x"></a>[C0-AM1 — MCP-native text evidence ingestion [x]](docs/history/PLAN.md#c0-am1--mcp-native-text-evidence-ingestion-x)

<a id="c0-am2--agent-friendly-wiki-operations-and-errors-x"></a>[C0-AM2 — Agent-friendly Wiki operations and errors [x]](docs/history/PLAN.md#c0-am2--agent-friendly-wiki-operations-and-errors-x)

<a id="c0-am3--protected-knowledge-spaces-x"></a>[C0-AM3 — Protected knowledge spaces [x]](docs/history/PLAN.md#c0-am3--protected-knowledge-spaces-x)

<a id="c0-am4--scoped-and-structured-knowledge-retrieval-x"></a>[C0-AM4 — Scoped and structured knowledge retrieval [x]](docs/history/PLAN.md#c0-am4--scoped-and-structured-knowledge-retrieval-x)

<a id="c0-am5--reliable-consolidation-and-maintenance-primitives-x"></a>[C0-AM5 — Reliable consolidation and maintenance primitives [x]](docs/history/PLAN.md#c0-am5--reliable-consolidation-and-maintenance-primitives-x)

<a id="c0-am6--agent-documentation-and-integration-tests-x"></a>[C0-AM6 — Agent documentation and integration tests [x]](docs/history/PLAN.md#c0-am6--agent-documentation-and-integration-tests-x)

<a id="final-c0-am-deployment-gate-x"></a>[Final C0-AM deployment gate [x]](docs/history/PLAN.md#final-c0-am-deployment-gate-x)

<a id="am3-runtime-acceptance--17-october-2026"></a>[AM3 runtime acceptance — 17 October 2026](docs/history/PLAN.md#am3-runtime-acceptance--17-october-2026)

<a id="am3-documentation-closeout-and-am4-start--18-october-2026"></a>[AM3 documentation closeout and AM4 start — 18 October 2026](docs/history/PLAN.md#am3-documentation-closeout-and-am4-start--18-october-2026)

<a id="am4-deployment-acceptance-and-documentation-closeout--18-october-2026"></a>[AM4 deployment acceptance and documentation closeout — 18 October 2026](docs/history/PLAN.md#am4-deployment-acceptance-and-documentation-closeout--18-october-2026)

<a id="am4-final-marker-gates-and-am5-start--18-october-2026"></a>[AM4 final marker gates and AM5 start — 18 October 2026](docs/history/PLAN.md#am4-final-marker-gates-and-am5-start--18-october-2026)

<a id="am5-deployed-runtime-acceptance--18-october-2026"></a>[AM5 deployed runtime acceptance — 18 October 2026](docs/history/PLAN.md#am5-deployed-runtime-acceptance--18-october-2026)

<a id="scoped-development-ci-policy--implemented-and-verified"></a>[Scoped development CI policy — implemented and verified](docs/history/PLAN.md#scoped-development-ci-policy--implemented-and-verified)

<a id="actual-development-and-negative-controls"></a>[Actual development and negative controls](docs/history/PLAN.md#actual-development-and-negative-controls)

<a id="full-acceptance-fixes-and-canonical-publication"></a>[Full acceptance, fixes and canonical publication](docs/history/PLAN.md#full-acceptance-fixes-and-canonical-publication)

<a id="am6--accepted-guidance-and-independent-workflows-19-october-2026"></a>[AM6 — Accepted guidance and independent workflows (19 October 2026)](docs/history/PLAN.md#am6--accepted-guidance-and-independent-workflows-19-october-2026)

<a id="source-review-and-full-acceptance"></a>[Source, review and full acceptance](docs/history/PLAN.md#source-review-and-full-acceptance)

<a id="accepted-dedicated-runtime-and-preservation"></a>[Accepted dedicated runtime and preservation](docs/history/PLAN.md#accepted-dedicated-runtime-and-preservation)

<a id="closeout-and-retained-limits"></a>[Closeout and retained limits](docs/history/PLAN.md#closeout-and-retained-limits)

<a id="integration-m19--optional-approved-client-metadata-discovery"></a>[Integration M19 — Optional approved client metadata discovery](docs/history/PLAN.md#integration-m19--optional-approved-client-metadata-discovery)

<a id="m19-core-implementation-checkpoint--21-october-2026"></a>[M19 Core implementation checkpoint — 21 October 2026](docs/history/PLAN.md#m19-core-implementation-checkpoint--21-october-2026)

<a id="m19-application-implementation-checkpoint--21-october-2026"></a>[M19 application implementation checkpoint — 21 October 2026](docs/history/PLAN.md#m19-application-implementation-checkpoint--21-october-2026)

<a id="m19-core-release-and-consumer-adoption--21-october-2026"></a>[M19 Core release and consumer adoption — 21 October 2026](docs/history/PLAN.md#m19-core-release-and-consumer-adoption--21-october-2026)

<a id="m19-application-ci-correction--21-october-2026"></a>[M19 application CI correction — 21 October 2026](docs/history/PLAN.md#m19-application-ci-correction--21-october-2026)

<a id="m19-final-candidate-validation-corrections--21-october-2026"></a>[M19 final-candidate validation corrections — 21 October 2026](docs/history/PLAN.md#m19-final-candidate-validation-corrections--21-october-2026)

<a id="m19-forced-ann-fixture-isolation--21-october-2026"></a>[M19 forced-ANN fixture isolation — 21 October 2026](docs/history/PLAN.md#m19-forced-ann-fixture-isolation--21-october-2026)

<a id="m19-deployed-acceptance-and-main-closeout--21-october-2026"></a>[M19 deployed acceptance and main closeout — 21 October 2026](docs/history/PLAN.md#m19-deployed-acceptance-and-main-closeout--21-october-2026)

</details>

### M21 self-service implementation checkpoint

Core source `6f1e4703f4d027c82ccb03ef8813efe30c650365` passes [full39760439788](https://github.com/Stell0/ns8-czero/actions/runs/39760439788), including local/producer/released-image and both native distributions. Independently downloaded reports verify Debian genuine predecessor upgrade21, Rocky installation26/three expected skips, eight browsers/privacy guards,25 accessibility contexts, three OAuth-query artifacts with zero candidates and five actual scan/SBOM pairs. The full promotion verifier passes. [Core publication39768193889](https://github.com/Stell0/ns8-czero/actions/runs/39768193889) completes successfully at that exact source. Immutable `core-v0.31.1` wheel SHA256 `ec2b9757d5a947f98bc9e743a6d7eb9f5227f59682d6a8a334ea201f5d03d13a`, archive SHA256 `1ee6154ae1e3ed8a1a90684e85d3897034d05cb98733f18611bee84141bcbb5e`; downloaded checksums match. This Core bridge is not the application/live candidate.

Application0.50.0 pins released Core0.31.1 and implements the planned human approval, default Reader/blocked-account UI and generated `.skill`/single-plugin ZIP page. Focused HTTP/download tests pass115 cases; the exact native Core-seeded first-connection/replay helper passes six local HTTP tests. Updated native browser tests download/inspect both archives, and native admission checks require a genuinely new Reader plus persistent blocking. Final full application/consumer/image/native validation, supported dedicated update and actual ChatGPT skill/plugin acceptance remain pending in draft PR32.

</details>


## WikiPlant backend track — M0 inspection

The operator requests reusable research projects through M0–M8, without live migration, deployment or schedule activation. See [compatibility audit](docs/projects/WIKIPLANT_COMPATIBILITY.md) for exact original revisions, capability matrix, ownership, sequential implementation and tests. Current status: M0 comparison recorded; baseline validation pending. Existing ingestion and protected spaces are reused. Historical acceptance and deployed images remain frozen.


### WikiPlant M1 — project foundation (implementation checkpoint)

Strict manifest/topic v1 contracts and a protected transactional project service
reuse existing typed objects, unique keys and knowledge receipts. Configuration
history is immutable; new managed types reject raw object/bundle writes. User
anchors require current Admin authority and recorded affirmative authorization;
adjacent topics need direct active user anchors; peripheral topics are terminal
with fixed weekly expiry. Parent cycles and silent archive reactivation reject.
Reference REST/MCP bindings and a read-only `/projects` overview preserve explicit
space selection, local DOM rendering, late-response and access-loss guards.
See [project contracts](docs/projects/PROJECTS.md). New default-released-Core
availability remains gated on immutable library publication and pin adoption.

Executed focused evidence: 15 schema/DST cases; 60 project/object/bundle cases;
one actual signed-HTTP contract test; 19 project/space controller cases. First
expiry fixture expected the following week despite a still-future same-day UTC
checkpoint; corrected the fixture, preserving the strictly-future algorithm.
The original-main local baseline passes 2045 actual Python/PostgreSQL/packaging,
185 Node, Go/schema, shell and 21 Robot dry runs. Baseline40286224042 is completed/
successful with exact-source full promotion proof; independent artifact inspection
is in progress. M0 bed8142 full40289915767 has successful local/images/scans and
pending both-native checks. Full M1 local candidate checks are running; no M1
CI/native, Core release, live instance or external-agent acceptance is claimed.


M1 validation follow-up: the initial broad candidate run recorded 28 failures /
2037 passes, all from frozen catalog-count assertions after adding five tools.
The original 77 input/output/authority/REST contracts remain checked exactly;
project operations have a separate explicit additive inventory. Updated counts
and matching replay/destructive/closed-world hints pass the focused actual SDK
and guidance checks. The current/legacy project SDK calls pass against signed
HTTP/PostgreSQL. The exact native project seed/readback/Reader recovery helper
passes through the actual local HTTP app with explicit test-module path setup.
All190 Node cases and21 Robot dry runs pass. Corrected full candidate Python
validation remains running; native project browser/backup checks are implemented
but have not yet executed. Mark synthetic generated native passwords with a test
prefix so public privacy review distinguishes the existing random fixture from
a literal credential. No real credentials or instance state are committed.

Independent downloaded baseline40286224042 inspection passes Debian21 upgrade,
Rocky26 installation/three expected skips/all8 browsers, 30 accessibility contexts,
eight privacy guards, three actual query artifacts with zero candidates and five
SARIF/CycloneDX pairs. Exact full promotion verification also passes.


M1 native correction: full40294384190 rejects Rocky for two stale acceptance
assertions: home navigation now contains eleven links, and the numeric
accessibility context allowlist omitted the new `projects` page. Actual project
setup/replay, revision2, literal hostile topic/title rendering and zero executable
HTML pass before that allowlist rejection. Debian native passes. Preserve the
failed source82ddb34 and private artifacts. A separate source correction updates
the exact navigation count and extends the existing numeric/privacy helper test
to projects; no runtime code, authority, limit or deployed image changes.
Fresh complete exact-source CI/native/privacy remains required before M1 acceptance.
M2 development stays preserved separately and pauses for this correction.

### WikiPlant M2 — common source ingestion checkpoint

The existing external ingestion distribution now provides seven reusable
collectors and an independently reusable publisher, with strict finite source
definitions, explicit protected-space/Admin approval, private OAuth/job reuse,
SHA-256 identities, immutable version provenance, source/cursor receipts and
readback/citation verification. Collector selection, publication and reasoning
remain separate. The project reader exposes source status; disposable native
recovery now compares connector/current/history/cursor state. See
[source contracts](docs/projects/SOURCES.md) for operations, limits and recovery.

Focused validation passes103 cases: adapters, actual signed HTTP/OAuth/SDK/Core/
PostgreSQL text and multipart PDF, lost response reconciliation, pending
extraction, changed/unchanged versions, immutable citations, cursor conflicts and
wheel/archive standalone installation. All190 Node cases pass. Complete local
validation is running. Exact-source M2 CI/native evidence remains pending.
No real sources, production spaces, migrations, schedule activation or live
instance changes have occurred. Default released-Core feature adoption remains
gated on final immutable library release/consumer verification.

M3 implementation subplan: retain one managed typed record per logical queue
item, workflow, daily budget, reservation and checkpoint. Existing unique keys
and transaction receipts acquire the established object/knowledge/authority
locks; no new database or orchestration engine is needed. Lease ownership and
fencing generations protect every workflow mutation; separate reservation and
external outcome records preserve uncertain calls and saved results. Test real
PostgreSQL races, five ordinary/ten urgent-only totals, causal child bounds,
copy/rename deduplication, fixed daily budgets, config changes, crash recovery,
revocation and independent project state before accepting M3.

M0 exact bed8142 full40289915767 is completed/successful and passes the
full promotion verifier. Independently downloaded actual native XML/job logs
and five scan pairs pass: Debian genuine upgrade21, Rocky installation26/three
expected skips/all8 browsers, eight privacy guards, 30 numeric accessibility
contexts and three actual OAuth-query artifacts with zero candidates.

M2 follow-up checks pass151 signed HTTP/MCP/space/guidance/ingestion cases and
99 adapter/client unit cases, plus two standalone wheel/archive installations.
The parent source snapshot now names the exact current complete part set and
retains immutable previous version receipts after a document shrinks. A strict
UUID-array transport mismatch and a client argument spelling error were caught
and corrected by that actual SDK regression. A denied space selection clears
the client selector. Private CLI dry-run/resume/status/verify and the exact
native seed/recovery helper pass through actual local signed HTTP/PostgreSQL.
All190 Node, Go/schema, five shell parser checks,272 documentation links and
21 Robot dry runs pass. Broad pre-final-source checks pass2096 cases; a fresh
complete validation of the final additions is running. No native M2 or actual
external scheduled execution is claimed.

M2 final broad local checks pass2101 actual cases. Subsequent final focused
checks pass116 actual signed-HTTP/PostgreSQL publisher and ingestion unit cases,
including independent same-label/same-content connectors, Atom alternate/inline
entries and Core-side rejection of credential-bearing URL queries. Final wheel/
archive checks exercise the installed `c0-projects` executable outside Core/app.
The original operator checkout remains unchanged except its pre-existing dirty
documentation; development is isolated in the separate clone. M1 corrected
Debian native passes; Rocky/final artifact acceptance is still pending.

M1 source2486de4 full40303681995 has successful local, producer, released,
scans, both-native and actual artifact-audit jobs. Independent downloaded
inspection passes Debian21 genuine upgrade and Rocky26 installation/three
expected skips/all8 browsers, eight privacy guards,32 accessibility contexts
and three query artifacts with zero candidates; five scan pairs pass. The
merge gate correctly rejects `ready_for_review_required` because PR38 is a
work-in-progress draft for the complete task. This is not promotion evidence.
Intermediate branch-only full dispatches preserve that PR review gate; final
ready-PR/current-source acceptance remains mandatory. A fresh branch-only
full dispatch of exact2486de4 has been requested. Further implementation is
pushed on `feat/research-projects-work`; the final complete history will be
delivered to the draft PR branch before final ready-PR validation. No gate is
weakened and no merge, release or deployment is authorized by the failed gate.

M2 additionally passes107 ingestion unit cases,43 browser fixture/privacy
helpers,191 Node cases and275 documentation links. New disposable browser
assertions cover stored partial connector coverage and post-revocation clearing.
Two actual PostgreSQL cursor tests verify retry recovery and configuration-hash
changes without inherited cursors/watermarks. Compatible Admin configuration
saves install additive managed record kinds without changing immutable schemas;
22 project/schema cases pass. Final source candidate CI remains pending.

M2 d2575cc branch run40312131525 local CI passes2113 actual Python/PostgreSQL/
packaging and191 Node cases; producer, released-Core compatibility and all five
scans pass. Both native jobs remain running. M1 branch run40311946100 local and
images/scans pass with both native jobs running. Neither full gate is inferred.

A new actual negative PostgreSQL/SDK regression against d2575cc proves reported
counts alone could advance a connector cursor. The follow-up requires explicit
verified part receipt IDs and joins actual ready, non-archived same-space source
versions with complete parent snapshot membership inside Core. It rejects
unknown/wrong receipts and unbacked counts. CLI coverage counts only complete
originals; the native recovery seed submits exact receipt IDs. Eleven signed
publisher cases and the exact native seed/recovery helper pass locally. Preserve
the negative evidence and frozen candidate; the correction needs fresh full CI.

The M2 receipt-proof correction passes130 actual signed HTTP/PostgreSQL,
space/native-helper, guidance and ingestion unit cases. No schema definition,
OAuth behavior, existing knowledge or deployed image changes. It is committed
separately; its exact-source full publication/native/artifact gate is required
before M2 acceptance and M3 implementation.

### WikiPlant M2 accepted source and M3 transaction subplan

Exact correction28f40f0 full40316218857 is completed/successful, with2114
actual Python/PostgreSQL/packaging and191 Node cases. Producer/released checks,
both native distributions and all five scans pass. Full acceptance verifier and
independent downloaded XML/job-log/scan inspection pass: Debian21 genuine
upgrade, Rocky26 installation/three expected skips/all8 browsers,32 accessibility
contexts, eight privacy guards and three query artifacts with zero candidates.
M1 exact2486de4 branch full40311946100 also passes its full verifier and the
same independent native/privacy audit. These are branch acceptance proofs, not
ready-PR promotion, Core publication, live deployment or external-agent proof.

M3 now implements bounded managed run/checkpoint, queue/admission, daily-window
and attempt/invocation records. Queue unique keys bind stable IDs and canonical
question identity. The existing content transaction locks serialize reservations
and preserve current-role checks; every workflow commit carries its actual
lease owner/generation. Daily windows retain consumed allowances and configured
limits across replay and timezone changes. Saved results awaiting merge cannot
reserve new attempts. All origins share scope/novelty/lineage/capacity policy;
terminal ancestry and +20/max-three expansion remain separate from urgency.
Add real PostgreSQL races, crash/reclaim/revocation, copy/rename, fairness and
ordinary/urgent budget cases, then exact REST/current/legacy MCP and native
recovery tests. No generative handler or second database is introduced.

M3 local validation passes the fresh full2132 Python/PostgreSQL/packaging cases,
plus34 focused final-source cases after the bounded question-comparison and
polling-renewal refinements. Those focused cases include actual database races,
current/legacy MCP conflict codes, grant revocation, source fencing including
omitted-lease rejection, result recovery and the exact native recovery helper.
Node192, Go schema compilation, five shell parsers,21 Robot dry-run cases and277
documentation links pass. The earlier reused-database full run has2129 passes
and two failures caused by one retained scheduled succeeded health job; bounded
SQL inspection confirms that identity/state. Its failed evidence is retained.
Fresh full validation passes without changing runtime job policy.

Managed records use existing storage/schema0021; Core/app versions and genuine
deployed predecessor digests remain unchanged. Source synchronization now binds
each connector to a run, so omitting a fence cannot bypass transferred ownership.
The disposable browser covers literal queue/run rendering and inactive-lease
rejection. Backup/update/restart/restore compare exact saved run, checkpoint,
queue, reservation, outcome and connector-binding records. Actual native and
artifact acceptance for this M3 source still requires its forthcoming full run.
No real C0/WikiPlant project data, schedules or deployed images changed.

### WikiPlant M3 acceptance and M4 monitoring subplan

Exact M3 fb9c4b7 full40333538357 completed successfully. Actual remote local CI
passes2133 Python/PostgreSQL/packaging,192 Node and21 Robot dry-run cases.
Producer/released-image/module/all five scans pass. Full acceptance verification
and independent downloaded report/job-log/scan audits pass: Debian genuine
upgrade21/zero skips, Rocky installation26/three expected skips/all8 browsers,
eight privacy guards,32 numeric accessibility contexts and three OAuth-query
artifacts with zero candidates. A transient GitHub artifact-storage503 resolved
on retry; failed private evidence remains outside Git. Original working files,
deployed predecessor images, live knowledge and all real schedules are untouched.

M4 will persist per-primary-topic/local-day monitoring separately from queue
budgets. Reserve queries/source inspections before external calls, retain their
observed outcomes, support fenced recovery and advance watermarks only after
verified successful coverage. Material results remain pending merge until M5's
stronger evidence/Wiki contract. Daily execution must complete mandatory primary
monitoring even with a full/blocked queue. Add actual PostgreSQL caps/concurrency,
failed/uninspected/old-article controls and fake-agent signed SDK workflows.

Extend existing product plugin/skill packaging with explicit project bindings,
setup/intake/lookup/research/tracking/daily/weekly/recovery instructions and
scheduler prompts/handoff. Keep read-only questions mutation-free. Reuse existing
OAuth and current tool metadata; no generative handler or arbitrary execution.
Support IANA local occurrence/cycle identity and bounded late scheduled recovery.
No real task is installed or enabled; external installation, authentication and
unattended execution remain unverified until observed. Source collection and
saved-result recovery retain their established receipts and authority checks.

M4 implements separately capped monitoring cycles/call history, successful
watermarks and current-fence recovery; successful daily queue work cannot skip
primary-topic coverage. Initialization retains its hard five-seed maximum even
with a larger configured ordinary budget. Reserved work requires fresh scope
assessment after configuration changes without replenishing its attempt slot.
IANA daily/weekly contracts retain logical missed-cycle identity separately from
actual-day allowances. Attributed runner observations install/enable nothing.

Project-bound private skill/plugin variants reuse existing package machinery,
canonical OAuth/space binding and a read-only CLI. The six explicit product
templates contain workflow prompts and complete external scheduler handoff.
Generated archives retain exact scope/version, reject tampered bindings and
preserve existing output files/symlinks. No actual external agent, host task or
unattended execution is claimed. Core/app/schema versions remain unchanged.

Final focused local validation passes30 actual PostgreSQL/SDK/native-helper and
wheel/archive distribution cases, including independent installations/migrations.
Twenty-nine current documentation/package/runtime-audit cases,193 Node cases,
Go schema compilation, five shell parsers,21 Robot dry runs,280 maintained links,
the generated Skill Creator check and77-file contribution privacy check pass.
The broad local run initially finds one generated-template documentation-link
failure; the template substitution correction and affected regressions pass.
That run continues while exact-source remote acceptance is prepared; it is not
claimed wholly successful. No runtime behavior was weakened to satisfy a test.

Disposable native fixtures now retain monitoring calls/history/coverage through
backup/update/restart/restore and exercise literal browser monitoring content.
Exact-source full CI, both actual native reports, query/privacy/scanner audits
and actual candidate-image Dive analysis remain required before M4 acceptance.
M5–M8 and final released-Core pin adoption remain outstanding. No live C0 or
WikiPlant data, real spaces/schedules or deployed predecessor images changed.

Independent M4 Skill Creator forward evaluation uses only the generated skill,
synthetic lookup/intake/recovery scenarios and current tool metadata. It makes
no production calls or mutations. Explicit project selection, read-only lookup,
untrusted-source handling and uncertain attempt allowances are preserved. The
example binding/current project services cannot be verified on the available
external connection; no external integration is claimed. Review identifies a
wording ambiguity: unavailable checkpoint services cannot produce durable
BLOCKED receipts. Prompts now distinguish unsaved capability reports, specify
connection/manifest discovery and return actual QUEUED source/version identities
while citations await extraction. Missing services never cause generic-object
substitutions or invented receipts.

A real formatter negative also shows frozen5e2432f rewriting a literal
template-looking project name. Substitution now completes trusted static links
before inserting user metadata; its regression preserves the literal name.
Thirty current package/documentation/runtime cases pass. The earlier exact
5e2432f remote full local job passes2162 Python/PostgreSQL/packaging,193 Node
and21 Robot dry runs; both native jobs remain in progress. Actual downloaded
five scan/SBOM pairs pass. Verified registry manifest/config and13 compressed
layer blobs match that source and app digest. Dive0.13.1 analysis/CI passes at
98.13% efficiency; the product layer contains exactly six byte-identical tracked
templates under UID/GID10001. A metadata-only Docker29 export fails inspection;
its evidence remains private, and direct verified registry blobs provide the
analysis archive without changing the image. The prompt/name correction needs
its own exact-source full/native/artifact acceptance before M4 completes.

### WikiPlant M5 evidence and reporting subplan (gated)

Corrected M4 f2a2a13 full40373013755 is completed/successful. Exact-source
full acceptance verification and independent downloaded XML/job-log/scan audits
pass:2163 Python/PostgreSQL/packaging,193 Node,21 Robot dry runs; Debian genuine
upgrade21/no skips, Rocky installation26/three expected skips/all8 browsers,
privacy8, numeric accessibility32, three query artifacts/zero candidates and
all five scan/SBOM pairs. Corrected app registry digest c5639e9c558d4216 matches
its manifest/config/all13 compressed blobs; exact six product files and actual
Dive analysis/CI pass at98.13% efficiency. Original5e2432f acceptance/evidence
is retained unchanged. M4 is accepted on the branch; no ready-PR promotion,
Core release, deployment, actual external-agent execution or scheduling is
claimed. M5 now proceeds under the following subplan.

M5 implementation starts only after corrected M4 f2a2a13 full40373013755 and
its downloaded native/privacy/scanner audits pass. This subplan records design
preparation while that acceptance is running; it claims no M5 implementation.

Reuse current source/passages, claims, immutable Wiki revisions and exact-target
annotations. Add strict individual result/finding/publication/report/membership
and delivery records in existing managed typed storage. Stable result identity
comes from the actual research attempt or monitoring cycle/scope, retaining
lost-response recovery without another investigation. Replace M3's deliberately
generic stored-result reference with actual same-project result/evidence/commit
verification. Replace M4's conservative pending-material gate with verified
result/cycle/passage/Wiki publication checks before watermarks advance.

Findings distinguish observed facts, supported inferences, hypotheses,
contradictions, outdated assertions and unknowns. Validate actual ready immutable
passages and claim links/revisions. Record bounded contrary checks with their
observed provenance, alternatives, coverage and limitations; unsearched/failed
checks cannot support consequential conclusions. Semantic judgments remain
external. Preserve historical contradictions and exact revision applicability;
new Wiki revisions receive no automatic predecessor verification.

Keep Markdown separate from page DTOs/metadata and reject serialized page
envelopes in project publication. Preserve valid fenced JSON examples and the
future offline legacy frontmatter contract. Reuse existing knowledge operations
and validate their actual stored revisions/hashes instead of another knowledge
engine. Any trusted composition uses the existing transaction/connection and
lock order, never nested public mutations or arbitrary execution.

Reports have stable project/type/local-date identity and individual substantive
result membership or saved appendix references. Validate completed-but-unreported
coverage at final save, exposing deferrals and concurrent changes. Preserve all
existing payload, operation and reference limits. Save/read back actual Markdown
and immutable Wiki revision before reporting persistence complete. Reports about
blocked daily runs must remain saveable without declaring failed monitoring
successful. Report publication can use its independent logical run and retries
must reuse the saved report without repeating research. External publication,
notification and human reading remain separate attributed observations.

Test real PostgreSQL evidence/claim/Wiki bindings, queued extraction rejection,
foreign-space and stale-revision denial, JSON-body regression, result recovery,
report omission/concurrent membership controls, publication failure recovery and
English/Italian readable output. Extend actual REST/current/legacy SDK and
disposable native recovery/browser evidence. Keep actual external agents and
unattended execution unverified unless independently observed. M6–M8 remain
outstanding; this task still authorizes no live deployment or migration.

### WikiPlant M5 implemented; exact acceptance pending

Core now persists individual findings/results/versions/publication proofs,
stable daily/weekly reports, substantive entry/appendix membership and independent
delivery observations. Seven additive REST/MCP operations preserve the frozen77
original contracts. Existing source/claim/Wiki/annotation services remain the
knowledge owners. Ready immutable passage hashes, actual claim revisions and
bounded contrary observations gate publication. Pending published results may be
explicitly re-reviewed at their current revision after claim changes/retraction
without another attempt; completed results remain immutable. Old findings,
publications and evidence remain available. New Wiki revisions need verification.

Report finalization rejects omitted completed evidence, abandoned draft membership
and stale scope coverage. Explicit deferrals remain due. Saved appendices require
an exact revision link. External result publication, notification and reading
have separate attributed observations; uncertain calls require reconciliation and
failed publication retries reuse saved research/report state. The deterministic
client publisher renders externally authored English/Italian or explicitly
localized prose, verifies saved identities and resumes lost responses. It never
generates conclusions, sends notifications or truncates oversized content.

Actual local verification:54 focused PostgreSQL/SDK/project/contract cases pass,
then23 current evidence/report invariants pass, including claim-change recovery,
scope changes and abandoned drafts. Two client validation cases,48 package/
documentation/native-fixture cases,193 Node cases, schema/shell checks and21
Robot dry runs pass. Exact native protected seed/readback passes through signed
local HTTP for Owner and Reader, retaining actual result/Wiki/report hashes and
a simulated failed publication. Generated documentation passes281 local links;
the complete84-file contribution privacy scan passes. The broader early run
passed2147 cases and failed28 stale109-vs102 tool inventory assertions; after
updating the additive contract inventory all28 affected cases pass. Exact-source
remote full/native/image/privacy acceptance remains pending and is required
before M6. No local skips or fake host outcomes are counted as real external-agent
or unattended execution. No live data, spaces, schedules or deployment changed.

M6 next, only after M5 acceptance: bounded weekly structural audits and durable
review cursors, exact-revision semantic rotation, peripheral expiry at a distinct
future weekly checkpoint, compact historical capsules, project events using
ordinary admission, bounded metadata-only release checks, and reader diagnostics
for last successful runs, latest report, current connector definitions and gaps.
Preserve existing limits, evidence, authorization and immutable historical state;
semantic judgments stay external and no runtime update is installed automatically.

### WikiPlant M5 accepted; M6 implementation

Exact bf13979 full40395011881 is completed/successful. The full acceptance
verifier and independent downloaded artifact audits pass:2189 Python/PostgreSQL/
packaging,193 Node,21 Robot dry runs; genuine Debian upgrade21/no skips, Rocky
installation26/three expected skips/all8 browsers; privacy8, accessibility32,
three query artifacts/zero candidates and five scan/SBOM pairs. Actual registry
manifest/config/all13 compressed layers match the source and app digest02a21bad.
All six product templates and both new Core modules match tracked bytes under
UID/GID10001; Dive enabled rules pass at98.13% efficiency. No ready-PR promotion,
Core release, dedicated deployment or actual external-agent execution is claimed.

M6 implements bounded durable structural audit steps, exact-revision semantic
rotation, immutable topic lifecycle history and compact peripheral archives only
at a distinct future weekly checkpoint. Calendar events retain date precision,
bounded daily/weekly/monthly recurrence and missed-refresh coalescing; generated
work uses ordinary admission and preserves lineage/depth. Release checks use
bounded external metadata and distinguish failed/incomplete retrieval from
up-to-date; they never install code. Reader diagnostics show pinned latest report,
actual successful daily/weekly runs, current connector definitions and gaps.
Expose trusted Core input schemas in tool metadata where dict fields previously
hid mandatory nested fields, retaining old-Core upgrade guards and all original
contracts. Test PostgreSQL recovery/concurrency, scope/fencing, partial audits,
calendar precision/recurrence, archive history, client metadata and UI access-loss
guards, then exact full/native/artifact gates before M7. No live migration or
schedule activation.

M6 implementation checkpoint:20 current focused PostgreSQL/SDK/collector/input
contract cases pass, including persistent release identity alerts, overlapping
maintenance cursors, bounded historical admission, exact-revision rotation and
distinct future archive checkpoints. The signed native protected seed/recovery
and related maintenance cases pass9, retaining actual audit/semantic/event rows.
Node195, schema/shell checks,21 Robot dry runs,283 documentation links and the
93-file contribution privacy scan pass. The broad fresh-database suite is running;
exact-source remote full/native/image/artifact acceptance is still required.
Generated weekly/recovery instructions name actual operations and preserve partial
coverage. No external provider, host task or production migration was executed.

M6 review follow-up: active-only queue selection must retain historical anchor
service counts for ordinary tie-breaking. Aggregate counts from all retained
queue history inside the authorized transaction; do not load completed rows into
the bounded active inventory or reset their service. A real PostgreSQL regression
uses two previously served investigations and two active approved anchors, then
checks the unserved anchor wins after current-scope reassessment. The original
7109f0d acceptance run is retained; corrected exact-source acceptance is required.
All22 current PostgreSQL maintenance/workflow cases pass after the correction.

### WikiPlant M6 accepted; M7 implementation

Corrected1000839 full40414161692 completed/successful. Exact remote verification
passes2205 Python/PostgreSQL/packaging,195 Node and21 Robot dry runs. The full
acceptance verifier and independent actual downloaded artifacts pass: Debian
genuine upgrade21/no skips, Rocky installation26/three expected skips/all8
browsers, privacy8, accessibility32, three query artifacts/zero candidates and
five scan/SBOM pairs. Actual registry manifest/config/all13 compressed layers
match app digest4539b905; four Core modules and six product templates match
tracked bytes and UID/GID10001/mode0644. Dive enabled rules pass at98.13%; vendor
findings remain app171/database414/UI11. No dedicated deployment, real external
agent or unattended execution is claimed. Frozen7109f0d evidence is retained.

M7 implements deterministic private project export with stable identities and
integrity checks, preserving actual source/Wiki revisions and available typed
history. Use existing APIs where complete; add only a fixed bounded Core export
reader for missing knowledge/alias/annotation shapes, with current space
authorization and no authentication/storage-path export. Detect concurrent or
partial collection; do not claim a multi-request transaction snapshot.

Implement safe bounded YAML for client configuration and raw WikiPlant snapshots,
an offline parser/dry-run mapping contract, explicit public-only static selection
and complete fabricated English/Italian reference projects. Extend authorized
C0-space sourcing to selected typed GitHub knowledge and test a third source
space without implicit graph access. Optional private GitHub collection requires
explicit worker authorization bound to repository/destination; preserve the
existing public-only default and keep credentials outside C0. Immutable connector
schemas must not be changed silently.

Test deterministic/tampered/partial exports, Markdown/metadata separation, legacy
IDs/provenance/lineage/receipts, cross-project budgets/cursors/reports/recovery and
revoked source access with real PostgreSQL and signed SDK requests. Extend native
readback and read-only diagnostics for unresolved scope decisions. Update the
matrix/readiness/docs, commit/push and require full exact CI/native/artifact
acceptance before M8. No live data, spaces, schedules, migration or publishing.

M7 implementation checkpoint: fixed read-only Core catalog/text fragments and
private two-pass export, offline raw-layout/parser/mapping validation, explicit
public static selection, bounded YAML, typed source subscriptions and optional
private GitHub replay consent are implemented. Both fabricated English/Italian
SDK/PostgreSQL daily+weekly+report+export cases pass; source instructions leave
configuration and one-attempt allowance unchanged. Actual third-space typed
knowledge updates retain old evidence; current source grants remain required.
Native seed/recovery now checks exact interchange identities and Markdown hashes.
Latest focused native/source/static cases pass37, bounded format/security cases
pass33, and completed raw Drive/GitHub fixtures pass13 after structural config
validation. Node196,21 Robot dry runs, schema/shell checks,286 documentation links
and152-file contribution privacy checks pass. A fresh broad PostgreSQL run is in
progress; exact committed full/native/image/artifact acceptance is still required.
M8 has not started. No real sources, migration, schedules or deployment executed.

M7 local broad run completed2239 passed in1096.81 seconds with a fresh isolated
PostgreSQL database and no failures. Collection preceded the final parser/static
negative cases and configuration hardening; the affected latest unit/native/SDK
checks above pass separately. Exact committed remote full acceptance will run
the complete final collection. Primary-agent review covered the fixed export
catalog/space filters, private replay consent before mutation, no-follow artifact
paths, canonical checksums, Markdown boundaries and diagnostics feed ordering.

M7 review follow-up: absolute URLs to the bound C0 host must use the same private
Wiki selection, cross-space denial and protected-source destination removal as
relative links. Resolve them against the snapshot's actual instance binding;
retain ordinary authored external public links. Unit and actual signed-SDK static
export regressions cover absolute private/foreign Wiki targets, selected-page
mapping and citation destination removal. Original3762652 full40430534952 remains
retained and is not final acceptance; the correction requires its own exact full
CI/native/artifact gate. No static output was deployed or published.

M7 final static review extends the same boundary to unsupported nested/multiline
brackets and all leading-frontmatter newline conventions. Reject ambiguous
constructs instead of preserving unchecked link/image syntax; omission labels
are plain text. The6030cb8 absolute-link run40432402922 is retained as intermediate
evidence. Final corrected source receives another full exact-source gate; no
started or intermediate run is acceptance of a later commit.

Final static follow-up passes20 current unit/actual signed-SDK cases. Code examples
receive the same link checks; a partial fence parser cannot exempt later real
links. Bare bound-instance URLs require explicit mapping/review, and linear
bracket patterns reject a131072-character malformed input within the bounded
regression deadline. This deliberately conservative subset is documented. No
new parser framework/dependency or server/runtime behavior is introduced.

### WikiPlant M7 accepted; M8 final acceptance

Final corrected b5e84bb full40433543339 completed/successful. The full verifier
and independent downloaded artifact audit pass:2262 Python/PostgreSQL/packaging,
196 Node,21 Robot; Debian genuine upgrade21/no skips, Rocky installation26/three
expected skips/all8 browsers, privacy8/accessibility32, three query artifacts with
zero candidates and five actual scan/SBOM pairs. Final app a1a675f8 source/config
and all13 registry layers verify; three Core modules, project controller and six
templates match tracked bytes/ownership. External worker/YAML packages are absent
from the server image. Dive enabled rules pass at98.13%; vendor findings remain
app171/database414/UI11. Earlier3762652/6030cb8 runs remain historical evidence.
Final static export deliberately rejects unsupported syntax and unchecked bound-
instance destinations. No live migration, deployment or external task occurred.

Frozen M7 candidate identities (disposable acceptance, not live deployment):
- Module sha256:603645ba7f441b270ea451c97e79312b5e09f1cdc95d146efc8377759acf5783
- App sha256:a1a675f8b712f6f853c1dcd0b0fea1b60a9fa91b23e74dea8c4d00b399ca795b
- Database sha256:4e047edfc3225fc7b60da96cdfb152117d1ea3a93d12ba038a5eda89e9406849

M8 subplan: finalize independent Core/worker distribution probes and contracts,
bump additive Core0.34/app0.53 and worker0.2 without a database-schema change.
Temporarily accept released0.33 plus local producer0.34 for exact prepublication
validation; keep the actual immutable released default visible. After complete
same-source local/full/both-native/artifact gates, publish immutable core-v0.34.0
through the existing verified library workflow, download/check its actual assets,
then adopt its exact tag/frozen app lock and compatible patch-only updater range.
Never clobber tags/assets or change frozen deployed predecessor images. This is
not an NS8 stable module release or production deployment.

Finish README/AGENTS/matrix/readiness with executed evidence and explicit limits;
prove wheel/archive project state survives repeated migration, source/claim/Wiki
export works without app/NS8, and installed worker CLI validates both YAML/raw
fixtures without server packages or C0 writes. Open the completed ready PR using
repository policy and require its exact full acceptance. Keep real external-agent,
unattended execution, dedicated reference deployment and migration unverified;
the complete installation/verification handoff is the authorized deliverable.

M8 focused validation passes69 actual packaging/version/SSO-wrapper cases. Both
Core distributions preserve project records through repeated migration and expose
actual immutable Wiki/source/claim exports with revoked-token denial. Both worker
distributions validate the two YAML/raw fixtures without server packages/writes.
Only current native health expectations move to0.53/0.34; all predecessor source,
versions and digests stay frozen. Node196,21 Robot dry runs, schema/shell,287 local
documentation links and156-file contribution privacy checks pass. Fresh broad
PostgreSQL validation is running; no prepublication CI or release is claimed yet.

M8 prepublication local broad validation completed2262 passed in1111.69 seconds
on a fresh isolated PostgreSQL database, with no failures/skips. Primary-agent
review verifies the additive version/range transition, unchanged schema/auth and
frozen predecessor digests, independent project export/grant/migration probes,
worker installation and explicit readiness limits. The consumer lock still binds
released0.33; this candidate is not a library publication or default adoption.
Commit/push and exact full/native/artifact verification precede the new Core tag.

### WikiPlant M8 prepublication accepted; released Core adoption

Exact `cd8e7a8ec1649c5ce8c02a1fc2a264f06d4df9a7`
[full40443878849](https://github.com/Stell0/ns8-czero/actions/runs/40443878849)
completed/successful. Actual remote local log records2262 Python/PostgreSQL/
packaging cases in1190.04 seconds,196 Node and21 Robot checks; schema/shell pass.
Downloaded native reports pass Debian genuine predecessor upgrade21/no skips and
Rocky installation26/three expected skips/all8 browser workflows. Full promotion
verification and independent artifact audit pass8 privacy guards,32 numeric
accessibility contexts, three OAuth-query artifacts/zero candidates and five
actual scan/SBOM pairs. Registry configuration/source/all13 layers and installed
Core/app/project modules/controller/six templates match exact bytes/ownership.
Worker/YAML packages are absent from runtime. Dive enabled rules pass98.1338%
efficiency at204561819 bytes; vendor findings remain app171/database414/UI11,
module/imageroot0. Historical failed/intermediate evidence remains outside Git.

Frozen M8 prepublication candidates (disposable acceptance, not live deployment):

- Module sha256:6273015e198ad854d6fda9d3c0fed9553452d4217d6d0de7a887ceda72d21798
- App sha256:1a41c422a9c1c634f18013df4e90924c2515fcfc231d74128e0287fcc3cec472
- Database sha256:8b0e8d3e540aef0e82cea3f5472184a853f4d0833718af514729ce8a481d2c8d

Immutable [core-v0.34.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.34.0)
points to that accepted source. [Publication40449147120](https://github.com/Stell0/ns8-czero/actions/runs/40449147120)
completed/successful with8 exact-artifact packaging cases. Actual downloaded
release assets equal verified distributions and SHA256SUMS. Wheel checksum
`adbfc9e0422935dcd470b258a633633320b577b1b88faffe0290397fc2f34de8`;
source archive `4dc21c553974c8ab4431b72982b5c1ed7628aafe0f07a528eaa98b0e2d234bd6`.
Six additional local actual-asset cases pass58.62 seconds, including reproducible
rebuild/clean installation and real PostgreSQL migration/state/grant probes.

Default app0.53 now pins this exact released tag/commit in its frozen lock, with
>=0.34,<0.35 and matching patch-only Renovate bounds. The independent original
fork example remains0.24. Clean frozen noneditable default installation proves
Core0.34/app0.53/project services outside the checkout, without worker/YAML/NS8
packages. Packaged Core bytes and genuine deployed predecessor are unchanged.
Final ready-PR exact-head full acceptance must pass independently; record its
actual proof on the PR, avoiding any inference from the earlier green source.
Adoption-focused source/release checks pass31 cases, maintained documentation
checks pass287 local links and public-contribution checks pass158 changed files.
Primary-agent review confirms only the exact released pin/lock, reviewed updater
bounds/test and acceptance documentation changed after publication; no packaged
Core bytes, schema, authority or frozen predecessor changed. This is an author
review, not an independent human review.

The compatibility/readiness reports distinguish implemented/local/disposable
C0/reference/external-agent/unattended states. Reference deployment, real agent
research, scheduled execution/notifications/reading and actual migration remain
separate operational gates. No live project data, spaces, schedules, knowledge,
Github projects, deployed images or website publishing changed.


## WikiPlant deployed backend and frozen predecessor

The operator approved PR39 and separately authorized its merge and dedicated C0
installation on 27 October 2026. [PR39](https://github.com/Stell0/ns8-czero/pull/39)
merged regularly as `c2280f576ba71dda723bc1afa11577f2fd251edd`, retaining the
accepted source commits. Its tracked tree equals the tested `50f4f41` candidate.
[Main40466342634](https://github.com/Stell0/ns8-czero/actions/runs/40466342634)
completed/successful, including canonical publication. Actual main logs record
2,262 Python/PostgreSQL/packaging passes in 977.60 seconds, 196 controllers and 21
Robot checks. Independently downloaded native reports pass Debian genuine
upgrade: 21 passes/no skips and Rocky installation: 26 passes/three expected skips/all eight browsers.
Full exact-source promotion and independent artifact audits pass eight privacy guards,
32 numeric accessibility contexts, three query artifacts/zero candidates and five
actual scan/SBOM pairs. All 13 app registry layers, installed project bytes/owners
and Core 0.34/app 0.53 metadata verify; enabled Dive rules pass at 98.1338%. Six fresh
registry reads verify all three main/latest aliases against the accepted source.

The supported targeted native update of only the dedicated C0 instance completed
in 27.37 seconds after a C0-only backup and actual full backup-data integrity read.
The existing owned backup plan was returned to its exact disabled configuration;
all other backup plans remain unchanged. Actual installed module/app/database
revisions and digests match the accepted immutable candidate before and after a
supported dedicated-manager restart (10.75 seconds). Trusted HTTPS readiness,
DB schema 0021, route, certificate validation, services and timer health pass.
The normal idle one-shot worker is enabled and not failed. No CPU-quota or interactive Playwright waiver was changed.

Both post-update and post-restart preservation checks retain all 28,077 original
stable rows across 40 domain tables, original columns/schema, configuration,
auth/retrieval hashes, mounts, schedules, original terminal jobs/attempts and ten
unrelated module identities. The live original-file corpus is empty; nonempty
file recovery remains covered by disposable native tests. Three original
background grants preserve fixed authority fields within the known-valid
observation window, allowing only normal activity/inactivity/refresh counters.
The observer never consumes a user's refresh credential. Five explicitly
selected authorized protected-space Wiki pages retain exact readback hashes.

Existing signed-in owner sessions work after both changes without masking a loss
through reauthentication. Separate fresh native sign-ins and authorized REST
profile/knowledge reads pass. The existing connected MCP client reads the same
account after update and restart. Server capability readback advertises 117
operations, including 40 project operations, and serves the project reader.
This host session still caches the older tool catalog: reload it before using
the new project tools. No registered connection settings, client permissions or
OAuth scopes were broadened. Other roles retain disposable-native evidence;
actual project research, packaged-project-skill use and unattended execution are
not established by these read-only live checks.

Actual bounded root app-journal audits use the verified module UID/container,
not empty Podman logs. Each change window contains 28 entries and successful
health, signed-in profile, native callback, token and MCP positive controls.
Both audits find zero OAuth queries, issued/generic credentials, JWTs or
tracebacks. Fresh delegated consent/scope upgrade was not exercised here; its
counter is zero. No new C0 delegated client or grant was created for acceptance.
Raw journals, credentials, cookies, account IDs and failed/private evidence remain
outside Git.

Freeze this genuine accepted installation as the next upgrade predecessor:

| Image | Frozen installed digest |
| --- | --- |
| Module | `sha256:f7c9e08849ad63d6f0bcddea5916d1bb2609116fb0d963d7392b1a7458a75cc1` |
| Application | `sha256:2f5756f52dbacb487dec16c29a9cf48f3dded50b7b2c97428fe6d7fa4e87feca` |
| PostgreSQL | `sha256:ec9e7bb8f6c39b81946cfe3775effe224e6d887d0fd3c9ecab4703a360a468a5` |

All three revisions are `c2280f576ba71dda723bc1afa11577f2fd251edd`;
canonical installed tag `ci-c2280f576ba71dda723bc1afa11577f2fd251edd-40466342634-1`.
Preserve the earlier e384bed predecessor, immutable Core 0.34 tag and all historical
acceptance. Documentation closeout images are not replacement runtime evidence.
The M8 readiness report is its earlier implementation-acceptance snapshot; this
separately authorized installation closes its reference-deployment gate only.
No real WikiPlant data was migrated, no project space initialized, no research
schedule activated, no existing knowledge changed and no static site published.

Review correction: isolate ordinary browser inactivity too. Snapshot existing ordinary native-session idle bounds once in migration0022 without extending them, keep new ordinary browser idle windows independent of delegated activity, and retain the original finite ordinary consent/grant maximum. The first frozen074c28c is not published; its run is retained. The corrected Core source needs fresh full/native checks.

Successful-sign-in replacement also retires the prior opaque cookie without revoking separately authorized grants. Old in-flight requests cannot restore browser access; authority cleanup retains unexpired finite grants too. The earlier2fd8631 remains unpublished, with its exact checks retained; the corrected release source must repeat full/native acceptance.

The2fd8631 Debian native run40511353228 exposed a disposable expiry fixture that updated only the absolute timestamp and violated the independent idle-window constraint. Update the exact fixture to expire both timestamps, retaining the runtime constraint. Its new actual renewable signed-HTTP recovery regression passes; new exact-source full/native gates are required.

The ingestion [M9 candidate](docs/ingestion-pipeline/M9.md) adds bounded progress,
unit diagnostics and controlled recovery, schema 0030. It passes 24 focused
Core/source HTTP cases, signed cookie/CSRF recovery, four migration controls,
211 existing plus four new JavaScript cases and the real 100-page/two-failure
browser flow. Broader full/native/independent-package acceptance remains separate.

The ingestion [M10 measurement candidate](docs/ingestion-pipeline/M10.md) adds
frozen-input extraction arms, read-only context comparison, owned PostgreSQL
restart/worker recovery and restored explicit-reindex proof. Original M4 exact
source `43af133` passes 2,677 full local cases, and M5 final `2afbe4a` passes
2,682, without database skips. Sequential full/native acceptance still applies.

The operator keeps ingestion model-quality acceptance open (2026-11-03); no
model turns are run. Other implementation and disposable acceptance continue.


### API-key producer acceptance and released Core

PR72 regularly merges as `a30d45c80948d0f7447ec887e9c74e9697304cf3`.
Exact source `2eb0b453f329f2f1044ff6151854298aac1b7e88` passes full/native
[41820035695](https://github.com/Stell0/ns8-czero/actions/runs/41820035695),
independent downloaded artifact grading and exact-source full promotion.
Debian upgrade21, Rocky install26/three expected skips, all native browser/privacy
workflows and five scan pairs pass. Original failed candidates/runs remain frozen.
The schema0015 bootstrap regression is corrected without weakening its test.

Core0.38.0 is immutably published at that source by
[41837683939](https://github.com/Stell0/ns8-czero/actions/runs/41837683939).
Downloaded public distributions and checksums match the prepared artifacts.
Schemas0031/0032 are additive; prototype keys from the first candidate are revoked
rather than acquiring reconstructed permission revisions. Existing OAuth and
knowledge remain unchanged. Actual producer main/full
[41828728776](https://github.com/Stell0/ns8-czero/actions/runs/41828728776) passes.

The app0.58 consumer adopts the released tag and immutable Git lock,
with >=0.38.0,<0.39.0 and matching patch-only updater bounds. It keeps creation
validation usable for Readers/Editors and redacts one-time keys in retained
browser traces/screenshots. No live update or stable NS8 module release occurs.


Consumer local validation uses the actual released Git Core: 26 focused
API/migration/privacy cases, 60 source/fork/runtime checks, 219 Node controllers
and all 24 real browser workflows pass. The published wheel's 95 runtime files
match the tagged Git source byte for byte; wheel/source assets match the
publisher-prepared bytes. Wheel SHA256 is
`2363fc717e82b7cdb6ab1e59598f94e4e829c7518f6ba962e9d7987376f489dd`;
source SHA256 is
`9ba30d4146beec2a42fedbe178554498362d8ce0f2b740e2e7f77f582fb9f3b9`.
The consumer keeps frozen Core package tree
`bd00a8d9bf7ee4b1d878d7d72d4172346951b4a2` unchanged.

### API-key released-consumer acceptance

PR73 exact source `00ffd370c0f9c9241eed26c91d7725078cea86e7` passes
[full41840958720](https://github.com/Stell0/ns8-czero/actions/runs/41840958720).
Its actual published/default application images verify the immutable released
Core Git source `2eb0b453f329f2f1044ff6151854298aac1b7e88`; the native suites
verify all three installed candidate images. The complete local job passes
2,775 Python/database/packaging cases, 24 real browsers, 219 Node cases,
schema/shell checks and 21 Robot dry runs, without database skips.

Independent downloaded artifacts pass Debian genuine-predecessor upgrade21,
Rocky installation26/three expected skips, eight native browser workflows,
eight privacy guards, 32 numeric accessibility contexts, all ten access stages,
three OAuth-query artifacts with zero candidates, and five scan/SBOM pairs.
The exact-source full promotion verifier passes while PR73 is open; the
Actions-owned merge gate then permits regular merge as
`1a92b7aebbec3c5ad217f03e84f2b57a250f9d18`.

Frozen consumer candidate tag:
`ci-00ffd370c0f9c9241eed26c91d7725078cea86e7-41840958720-1`.

| Image | Candidate digest |
| --- | --- |
| `czero` | `sha256:b74252d9524ab8943492907af63ada6d85008054555c84a639d17e6161a9ec53` |
| `czero-app` | `sha256:0f98d7eb6ddf4e6774f16d5afe28fcff55b2003df61d53402806dee14c882b99` |
| `czero-postgres` | `sha256:ab69d3553b77a483b57f11125175ca5da230858720aa3e2c1277e6c613c3a069` |

Producer merged-main41828728776 also passes independent downloaded artifact
grading and six fresh registry reads against its accepted images. Preserve all
earlier failed/local evidence privately; it is not substituted for accepted CI.
Actual consumer merged-main
[41851447750](https://github.com/Stell0/ns8-czero/actions/runs/41851447750) passes
all full/native jobs, the Actions-owned merge gate and canonical publication.
The source has the same tracked tree as the accepted consumer candidate:
`f0c39edad1ba66dcd7612bfd69fdf8a35022b754`.
Its local counts and independently graded native/browser/privacy/access/scan
results match the candidate counts above. The actual published application image
selects released Core0.38.0 from the immutable Git lock and passes the runtime
source/schema probe; the native suites verify that image's digest.

Frozen merged-main tag:
`ci-1a92b7aebbec3c5ad217f03e84f2b57a250f9d18-41851447750-1`.

| Image | Merged-main digest |
| --- | --- |
| `czero` | `sha256:0c68d56d754b78f7e78ebdf52a0f361e242b0f3ca41b78d688ff08324efedb9c` |
| `czero-app` | `sha256:9463a0eb90011ad36f8b797ba7ee2c8813f1850805278a6ad7927fc58630d2c8` |
| `czero-postgres` | `sha256:ec06e6021deecc4f6fa97dbb8123e26056426369f989e89322ba7cffe384f9e9` |

Six fresh registry manifest reads at 15:46–15:47 UTC on 4 November 2026 verify
each image's `main` and `latest` tag against these independently accepted digests.
This is source/publication acceptance, not a live installation or stable module
release. Keep these immutable identities when documentation main advances.

**Historical promotion-tool failure, resolved by PR75:** the original
`verify-promotion.py --source 1a92b7aebbec3c5ad217f03e84f2b57a250f9d18 --full`
check rejected `actual_required_jobs_missing`: its broad `native /` match included
the optional skipped Debian screenshot publisher. Both actual native suites,
artifact grading and the Actions-owned gate passed. Preserve that failed check.
PR75 commit `bd0ffc28cf6f400e3730e82880b3a436c8de25b1` requires both actual
native suites exactly once and excludes optional screenshot publishing jobs.
All 155 policy/promotion checks pass, including 12 new regression cases; the
corrected full command verifies historical main run `41851447750`. This repair
does not replace current-source acceptance or grant deployment authority.

The installed app0.57/Core0.37/schema0030 runtime at
`5e89055de12f46b2e87325d8fee1e6ee59dfa15d` remains the live baseline.
