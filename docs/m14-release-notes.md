# M14 development deployment notes

This candidate hardens the completed C0 reference application. It is not a stable
NS8 module release. Core/app/schema remain 0.24.2/0.39.0/0013; public REST/MCP and
stored data contracts are unchanged.

The initial reference application includes native NS8 configuration/TLS/status,
application SSO and Reader/Editor/Admin membership, typed records/forms/relations,
deterministic document ingestion with immutable evidence/citations, versioned
Wiki pages/entities/claims/graphs, provider-free full-text search and optional
embeddings/Jev/Kev fallback, deterministic jobs/schedules, OAuth-consented
REST/MCP access and caller-aware agent discovery. Core artifacts, managed-file
upgrades and repository skills support independent forks. Native encrypted
backup/clean restore and predecessor updates preserve their documented data
contracts. Real external-provider answer quality and actual ChatGPT/scheduled
client interoperability are not established by the mock/SDK acceptance suites.

- Update compatible native UI dependencies and supported database OS packages.
- Remove the database's unused root-only gosu executable while preserving package
  and license metadata.
- Add native container memory, swap and task limits, drop capabilities and forbid
  privilege escalation. Container CPU quotas are explicitly deferred after a
  real rootless-controller startup failure; the candidate omits that flag.
- Keep complete vulnerability reports and CycloneDX SBOMs, and fail publication
  for fixable critical findings after uploading evidence.
- Add effective installed resource/privilege measurements, bounded HTTPS health
  and search latency acceptance, and actual-browser accessibility smoke checks.
- Pin disposable SSO fixtures to versioned IdP 0.3.1 and LDAP proxy 1.4.0, with
  complete native compatibility acceptance. Live provider/proxy configuration
  is unchanged.

Upgrade only the dedicated C0 instance through the supported NS8 update action,
using the frozen candidate tag after verifying all image digests/source labels in [the readiness report](m14-readiness.md).
Verify native readiness/configuration, owner authentication, retained application
data, scoped MCP and the worker timer after update and full manager restart.
A successful update action alone does not prove runtime readiness.

Existing encrypted NS8 backup and clean-restore contracts remain. Test destructive
recovery and uninstall scenarios in disposable instances. See the readiness
report for unresolved security findings, external interoperability limits,
acceptance results and the explicit CPU deferral.
