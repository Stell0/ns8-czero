# Generic structured tables

## Problem and implementation

A space can contain typed records without Wiki pages. Its home must expose populated
collections instead of presenting Wiki absence as absence of all data. The Tables
navigation leads to a paginated selected-space collection directory. Each collection
has a `/tables/:type` page; existing `/explore/records/:id` links continue to work.

The Vue website uses existing Nebula components. Columns come from immutable
registered schemas, including schema titles and optional properties. Up to six scalar
columns are initially visible; types with only structured fields instead expose
those fields immediately. The column chooser exposes all fields. Nested values
expand recursively on demand, with complete strings available after expansion.
Arrays of objects render child tables, and the Nebula drawer
shows the complete selected record with metadata and a link to relationships.
Missing, null, empty strings, false and zero remain distinct. Text is never HTML.
Payload dates, encoded JSON strings and foreign keys are not inferred.

Filters use existing exact structured predicates and tags. A filter value is parsed
according to the selected scalar schema field. Filtering and sorting run on the
server over all matching records before paging. Page size is 50, with Previous/Next;
no mandatory full collection counts or browser-wide dataset download are introduced.
The collection directory also pages independently. Query state follows browser
navigation. Record data uses the existing account/space/generation query identities,
request cancellation and access-loss clearing. English/Italian and themes reuse
existing website infrastructure.

## Additive Core and transport contracts

`ObjectService.list_types(..., populated_only=False)` retains the legacy global
catalogue by default. With true, it checks current selected-space Reader authority
and returns schemas for which records exist in that space. It does not scan other
spaces or grant access. Pagination is bounded by the existing limits (1–100 rows,
offsets 0–100000). No per-type browser fan-out or stored catalogue is needed.

REST/MCP `object_types_list` adds optional `populated_only` and `space_id`. The
website always passes its selected space. Ordinary global type discovery remains
compatible. `objects_list` adds optional `sort` and `direction` (`asc`/`desc`). Sort
selects a top-level scalar schema property or `@created_at`, `@updated_at`,
`@revision`; nested/object/array/unknown fields are rejected. Numbers and booleans
use typed comparisons. Both null and missing values sort last in either direction;
record ID breaks ties. Omitted sort retains the existing `created_at,id` order.
Identifiers and direction are validated; field values remain SQL bound parameters.
Existing exact filters, tag constraints, scopes, persisted membership and selected
space authorization remain authoritative. Responses and operation names are unchanged.

The reusable ingestion client retains global schema discovery before selecting a
space. Populated discovery and explicit space selectors still require the saved
selected-space binding; no ordinary content call gains a global exception.

Existing database indexes support space/type discovery. No migration or generic
per-field indexing is added. Large collection workloads require query-plan review
before adding workload-specific indexes. Internal timeouts remain unchanged.

## Delivery gates

Core0.49 is immutably published at `core-v0.49.0` from source `998ef32`, after
full/native/packaging acceptance and publisher43318027771. App0.67 selects that
released tag and frozen Git lock, with >=0.49.0,<0.50.0 and matching patch-only
updater bounds. The committed Core tree equals the released source tree; reference
CI therefore selects released Core. Repeat consumer/full/native acceptance before
promotion. This source candidate does not authorize production deployment.

Tool descriptions document the optional selectors. Historical contract checks
validate the exact additive fields before projecting to the frozen legacy schema;
authorization, responses and old parameters retain their comparisons. Existing
end-user skills already select spaces and schemas correctly; no new permission or
plugin package inventory is required by these optional browsing parameters.

## Validation

Synthetic fixtures exercise populated versus empty types, numeric ordering across
pages, missing values, invalid sort rejection, selected-space discovery and denial,
REST schema/catalogue/sort contracts, nested values and inactive markup. Browser
fixtures cover records without Wiki, paging, navigation, details, phone width and
clearing records after denial. The existing installed record-reader workflow also verifies real collection discovery,
server filters/sorting, details and inactive markup as Admin and Reader. Artifact
audits require both Tables accessibility contexts in addition to existing checks.
Full runtime/native acceptance and released-consumer
proof remain required before release or deployment. Executed checks are recorded
in the pull request, with failed runs retained outside Git.
