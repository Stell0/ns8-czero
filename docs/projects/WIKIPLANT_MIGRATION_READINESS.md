# WikiPlant migration readiness — implementation checkpoint

**Not ready for migration.** M0/M1 foundations and M2 source collection are
implemented candidates. M3–M8 are still outstanding. This file is an explicit
checkpoint and will be replaced with executed final acceptance evidence.
No real WikiPlant data, live C0 knowledge, real project spaces or schedules have
been migrated, modified or activated by this task.

Inspection inputs: C0 `631293d50de6f0faa914554455dbfe61ce623764`, WikiPlant
`e8dd9e7ae9b48d028cf9a735b30490749c3d8d6c`. Public scaffold inspection does not
verify canonical production instance names. Reference projects remain synthetic.
See the [compatibility matrix](WIKIPLANT_COMPATIBILITY.md),
[project contracts](PROJECTS.md), [source contracts](SOURCES.md) and PLAN.md.

| Feature | Implemented | Tests | Integration verified | Known limitations | Migration blocker |
| --- | --- | --- | --- | --- | --- |
| Protected manifest/config history | yes | passed locally | no | Exact both-native M1 acceptance pending; default released Core adoption pending | yes |
| Topics and structural scope governance | yes | passed locally | no | Semantic assessment remains an external-agent responsibility | yes |
| Project reader/config/topics/source status | yes | passed locally | no | Full native/browser candidate acceptance pending; workflow/report views await their records | yes |
| Seven source adapters and private CLI | yes | passed locally | no | Bounded configured selections; no real sources contacted by acceptance fixtures | yes |
| Immutable source/snapshot/cursor receipts | yes | passed locally | no | One private job per connector; source/run coordination is extended in M3; pending extraction remains incomplete | yes |
| Durable queue/budget/reservations/fencing | no | not_run | no | M3 outstanding | yes |
| Mandatory primary monitoring | no | not_run | no | M4 outstanding; never substitutes for queue work | yes |
| External-agent skills and scheduling handoff | no | not_run | no | M4 outstanding; no external task installed or execution observed | yes |
| Results/evidence/report completeness | no | not_run | no | M5 outstanding | yes |
| Maintenance/calendar/archive/rotation | no | not_run | no | M6 outstanding | yes |
| Project/static export and offline migration preparation | no | not_run | no | M7 outstanding; no production export/import authorized | yes |
| Complete synthetic end-to-end acceptance | no | not_run | no | M7/M8 outstanding | yes |
| Core release/default consumer adoption | no | not_run | no | Producer implementation only; new operations explicitly reject unavailable old Core | yes |
| Actual external-agent research execution | no | not_run | no | Separate authenticated observed execution required | yes |
| Unattended scheduled execution/readback | no | not_run | no | Configuration or prompt generation cannot prove host installation/authentication/execution | yes |

Evidence levels stay separate:

- Implemented code: M1/M2 candidate on the development branch.
- Local validation: actual PostgreSQL, signed HTTP, OAuth, current/legacy MCP,
  CLI and packaging tests; no database skips counted as passes.
- Disposable native C0: M0 full baseline audited; M1 corrected Debian upgrade
  and Rocky installation/all eight browsers pass with independent privacy audits.
  Its draft-PR merge gate rejects as intended; branch acceptance is pending.
- Dedicated reference instance: no project implementation deployed or tested.
- Actual external agent: no project workflow execution observed.
- Unattended scheduling: no task installation, execution, notification or human
  reading observed. These are independent observations.

Existing CPU-quota and interactive Playwright waivers remain unchanged. Failed
private evidence is retained outside Git. Historical deployed image digests and
accepted source evidence remain untouched.
