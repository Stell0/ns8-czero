# WikiPlant migration readiness — M7 checkpoint

**Migration is not yet accepted.** M0–M6 have completed their exact full/native
acceptance. M7 code and focused tests are implemented; its full gate is running.
M8 Core release/default adoption and final PR acceptance remain outstanding.
No real WikiPlant data, live knowledge, project spaces, schedules or deployments
have been changed. The existing Github projects space is untouched.

Inspected C0 main: `631293d50de6f0faa914554455dbfe61ce623764`.
Inspected WikiPlant main: `e8dd9e7ae9b48d028cf9a735b30490749c3d8d6c`.
Public scaffold inspection does not verify production canonical names.
See [compatibility](WIKIPLANT_COMPATIBILITY.md), [projects](PROJECTS.md),
[sources](SOURCES.md), [workflows](WORKFLOWS.md), [monitoring](MONITORING.md),
[reporting](REPORTING.md), [maintenance](MAINTENANCE.md) and [export](EXPORTS.md).

| Feature | Implemented | Tests | Integration verified | Known limitations | Migration blocker |
| --- | --- | --- | --- | --- | --- |
| Protected manifest/configuration/history | yes | passed | yes, disposable C0 | Default released Core adoption pending | yes |
| Topics/scope/classification/lifecycle | yes | passed | yes, disposable C0 | Semantic assessments stay external | no |
| Project read-only overview/diagnostics | yes | passed | yes, disposable browsers | M7 scope/release diagnostics full gate pending | yes |
| Seven reusable source adapters/CLI | yes | passed | yes, disposable C0 | Real source/provider quality not evaluated | no |
| Source versions/readiness/cursors/provenance | yes | passed | yes, disposable C0 | Binary originals require existing upload/backup paths | no |
| Typed C0 subscriptions/private GitHub consent | yes | passed | yes, local signed SDK | Remote GitHub responses mocked; M7 full gate pending | yes |
| Queue/admission/budgets/reservations/fencing | yes | passed | yes, disposable C0 | External calls can remain uncertain | no |
| Primary monitoring independent of queue | yes | passed | yes, fake agent/disposable C0 | No actual external search host observed | no |
| IANA scheduling/skills/prompts/handoff | yes | passed | no, external host | No task installation/unattended authority observed | yes |
| Evidence/results/Wiki/revision validation | yes | passed | yes, disposable C0 | Semantic truth is not deterministic validation | no |
| Daily/weekly saved reports/readback/delivery state | yes | passed | yes, disposable C0 | Actual publication/notification/reading unobserved | no |
| Weekly audits/semantic rotation/archives/calendar | yes | passed | yes, disposable C0 | Bounded semantic batch is not complete semantic audit | no |
| Private project export/integrity | yes | passed | yes, local signed SDK | M7 full gate pending; change detection is not a snapshot | yes |
| Offline WikiPlant parser/migration manifest | yes | passed | no, production data | Synthetic raw fixtures only; no target binding/import | yes |
| Explicit public static export | yes | passed | yes, local signed SDK snapshot | Conservative Markdown subset; no publishing | no |
| Complete English/Italian synthetic daily/weekly/export | yes | passed | yes, local signed SDK | Fake agents, mocked remote inputs; M7 full gate pending | yes |
| NS8 restart/backup/restore/upgrade preservation | yes | passed | yes, disposable native | M7 export readback native gate pending | yes |
| Core release/default consumer adoption | no | not_run | no | Producer candidate only | yes |
| Ready PR/current full acceptance | no | not_run | no | M8 outstanding | yes |
| Actual external-agent research | no | not_run | no | Separate observed authenticated execution required | yes |
| Unattended scheduled execution/readback | no | not_run | no | Complete handoff exists; host capability unverified | yes |

Evidence levels remain separate:

- **Code:** M1–M7 implemented in the development branch; M7 not yet accepted.
- **Local tests:** actual PostgreSQL transactions/authorization/concurrency,
  signed OAuth/SDK/REST/MCP, CLI, parsers, packaging and Node controllers.
  The two synthetic end-to-end cases pass with real persisted evidence and
  English/Italian reports; fake provider results prove no actual external agent.
- **Disposable native C0:** M6 corrected `1000839` full run
  [40414161692](https://github.com/Stell0/ns8-czero/actions/runs/40414161692)
  completed successfully:2205 Python/PostgreSQL/packaging,195 Node,21 Robot;
  Debian genuine upgrade21/no skips, Rocky installation26/three expected skips,
  all8 browsers/privacy guards,32 accessibility contexts and three actual
  zero-candidate OAuth-query artifacts. Independent image/scan audits pass;
  known vendor findings remain app171/database414/UI11. See PLAN.md for all
  earlier milestone sources, CI and frozen candidate evidence.
- **Dedicated reference instance:** no project implementation deployment/test.
- **Actual external agent:** no project execution observed.
- **Unattended scheduler:** no installation, execution, notification or human
  reading observed. Configuration and saved reports cannot prove these states.

Existing CPU-quota and interactive Playwright waivers remain unchanged. Private
failed evidence stays outside Git. Historical deployed digests/acceptance records
are preserved. M8 will replace this checkpoint with final executed evidence and
remaining external-platform blockers. Real migration remains a separate task.
