# Verified development installation candidate

This is a reviewed development candidate, **not a stable NS8 release**. It is the accepted M19 runtime; M21 documentation/plugin changes are still being tested. A new operator can use this record without the historical maintainer runbook. Existing installations should back up and follow the targeted update procedure in [Administration](administration.md).

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
