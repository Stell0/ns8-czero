# Select a verified development installation candidate

C0 has no stable NS8 module release. Select an immutable candidate whose actual full/native acceptance passes and whose features fit your use. Moving `main`/`latest` tags are development channels. Do not infer installed features from the newest source manifest or from a documentation merge.

## Released-consumer candidate

The accepted document-BM25 consumer-main candidate in [PLAN](../PLAN.md#document-bm25--released-core-consumer-adoption) selects released Core0.44.0/schema0036 with app0.62.0. Its full/native/publication acceptance is recorded in [run42413222963](https://github.com/Stell0/ns8-czero/actions/runs/42413222963). Later source can contain additional producer capabilities without publishing or deploying them.

| Item | Accepted identity |
| --- | --- |
| Source | `59fcc3cf6b89799ba121a50e5721ac45a3e36df5` |
| Immutable tag | `ci-59fcc3cf6b89799ba121a50e5721ac45a3e36df5-42413222963-1` |
| Module | `sha256:94c341a2cd9217cbe6c7a2637000d4a8f58c14e5a42f0b313bfdd0a8b0b8e13e` |
| App | `sha256:92222434751765ad020bb06f4e7093d514474b033e4192e153260f5d02b872cd` |
| PostgreSQL | `sha256:4629070c3acba1995bfb42af1db253011efc9266648d0bf4723469fc15de3f1a` |

From the NS8 leader, replace `<node-id>` with your selected node:

```sh
add-module ghcr.io/stell0/czero:ci-59fcc3cf6b89799ba121a50e5721ac45a3e36df5-42413222963-1 <node-id>
```

Follow [Administration](administration.md) for hostname, trusted HTTPS, sign-in provider/user domain and owner configuration. The measured native platform matrix is Debian13 and Rocky Linux9. Check the exact candidate's current acceptance and registry availability before installation. Existing instances require a supported backup and explicit update; the destructive latest-only migration needs [preflight](latest-only-migration.md). Do not mix independently selected module/app/database images.

The accepted installed runtime is recorded separately in PLAN. This document selects an accepted source/publication candidate; it does not change any installed baseline, enable compilation/OCR or install schedules.

<details>
<summary>Preserved earlier installation evidence</summary>

## Historical M19 candidate

The following frozen record describes the original M19 checkpoint. Its identities and measured platform/IdP fixture remain historical evidence. It does not supply the features described in the current guides.

| Item | Accepted identity |
| --- | --- |
| Source | `38a8654486581e0f2af21672e8675a2e925d2b38` |
| Canonical tag | `ci-38a8654486581e0f2af21672e8675a2e925d2b38-39613259374-1` |
| App / Core / schema | `0.49.0` / `0.31.0` / `0018_cimd_clients` |
| Module digest | `sha256:0a78eef9a6cfd6246e495c88d4f95ecbc1c6daaf7bb38d3d0e003ffbe82db7fb` |
| App digest | `sha256:4b2000d645cb9f6d7a508365d770d37db2cc085af113340c635f89e79bd23d9b` |
| PostgreSQL digest | `sha256:d8beafaa39c490e9046e4611b298a7cd8ab87ef7400ac1adbd84a2a32d9cecf2` |

On the NS8 leader, replace `<node-id>` with the selected node's numeric ID:

```sh
add-module ghcr.io/stell0/czero:ci-38a8654486581e0f2af21672e8675a2e925d2b38-39613259374-1 <node-id>
```

The accepted native matrix is **NS8 on Debian 13 and Rocky Linux 9**. Disposable native SSO tests use the NS8 IdP/Keycloak module **0.3.1** with ldapproxy **1.4.0** and an internal LDAP domain. This is the measured fixture baseline, not a claim that every external IdP/domain combination is supported. Use an already configured compatible NS8 user domain and IdP; coordinate platform/provider changes separately rather than replacing shared services for this install. Hostname-root DNS and publicly trusted HTTPS must be reachable by ChatGPT.

[Exact candidate CI](https://github.com/Stell0/ns8-czero/actions/runs/39613259374) and [main CI/publication](https://github.com/Stell0/ns8-czero/actions/runs/39632626515) passed; actual native, installed-image, browser/privacy and scan artifacts were inspected. The [readiness checklist](release-readiness.md) distinguishes these runtime facts from unfinished M21 web-plugin acceptance and broader release obligations.

</details>
