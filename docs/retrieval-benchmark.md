# Provider-free document retrieval

Core 0.44.0 is immutably released at `bb882504fb5ab3b94f10bd1d286b06fa81b004ea`
using schema0036. Producer full/native/browser/packaging acceptance passes;
app0.62 released-consumer full/native/browser/image acceptance passes. Existing
installed images remain unchanged. The measured SciFact baseline below remains development evidence.

## Published results

The final matched comparison below evaluates the released Core 0.44.0 document
BM25 ranker against the preceding lexical implementation. It improves document
ranking on SciFact, NFCorpus and a private documentation corpus. These are
retrieval measurements, not generated-answer accuracy or production latency.
The historical runs below remain available with their original settings and
limitations; their timings should not be mixed with this comparison.

### Provider-free text retrieval

| Corpus | Documents | Queries | Method | nDCG@10 ↑ | Recall@10 ↑ | Empty results ↓ | Core-call P95 ms ↓ |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| SciFact | 5,183 | 300 | Baseline | 0.3098 | 0.3372 | 156/300 (52.00%) | 149.0 |
| SciFact | 5,183 | 300 | Document BM25 | **0.6782** | **0.8073** | **6/300 (2.00%)** | **91.6** |
| NFCorpus | 3,633 | 323 | Baseline | 0.2365 | 0.1024 | 82/323 (25.39%) | 128.7 |
| NFCorpus | 3,633 | 323 | Document BM25 | **0.3206** | **0.1538** | **18/323 (5.57%)** | **56.8** |
| Private documentation | 251 | 50 | Baseline | 0.5250 | 0.6444 | 11/50 (22.00%) | 148.0 |
| Private documentation | 251 | 50 | Document BM25 | **0.6631** | **0.8407** | **0/50 (0.00%)** | **115.9** |

Higher nDCG means relevant documents appear nearer the top; Recall@10 measures
the fraction of labelled relevant documents found in the first ten distinct
documents. Empty results count queries returning no candidates. Quality scores
are macro averages; empty rankings score zero. Documentation quality uses the
45 queries with positive relevance labels, while empty-result counts cover all
50 questions. See the [metric definitions](../benchmarks/retrieval/README.md#valid-comparisons-and-reports).

The two methods use the same complete corpus and metadata, source-only selection,
response limit 50 and reranking off. Neither text method calls an embedding or
scoring provider. P95 covers Core calls on the same host with a contemporaneous
baseline; it excludes public HTTP/network/provider overhead and does not establish
cold-cache performance, statistical significance or performance on other hardware.
Baseline lexical, retrieval and citation helpers are all frozen at
`b8ec5bfe8883168234535c4113f2e52c1b1d887e`; the accepted ranker is
`bb882504fb5ab3b94f10bd1d286b06fa81b004ea`, published as
[Core 0.44.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.44.0).

| SciFact acceptance condition | Required | Observed | Result |
| --- | ---: | ---: | --- |
| nDCG@10 | ≥0.60 | 0.6782 | Pass |
| Recall@10 | ≥0.65 | 0.8073 | Pass |
| Empty-result rate | ≤10% | 2% | Pass |
| P95 / matched baseline P95 | ≤1.5× | 0.61× | Pass |

SciFact queries had already been inspected and are development evidence.
NFCorpus was first evaluated after candidate `4595054` was frozen; its final
rerun is an exposed-set confirmation, not a new holdout. Both NFCorpus quality
metrics improve against the baseline. No thresholds or relevance labels were
relaxed to obtain these results.

### Candidate recovery and hybrid ranking

The following SciFact values measure the distinct documents actually returned
within the response limit, not all indexed documents or internal candidates.
Oracle nDCG is the best possible ordering of those returned documents using the
known relevance labels; it is a diagnostic ceiling, not an achieved ranker score.

| SciFact diagnostic | Baseline | Document BM25 |
| --- | ---: | ---: |
| Returned-candidate recall | 0.3483 | 0.8802 |
| Oracle nDCG@10 | 0.3495 | 0.8819 |
| Mean distinct returned documents | 3.19 | 48.68 |

A separate fusion audit uses the same frozen arrays of 64 real semantic
candidates per SciFact query for every comparator, with reranking off:

| Ranking | nDCG@10 | Recall@10 |
| --- | ---: | ---: |
| Semantic-only | 0.7133 | 0.8559 |
| Baseline hybrid | 0.7198 | 0.8592 |
| Document BM25 hybrid | **0.7388** | 0.8536 |

Hybrid passes the requirement to stay within 0.01 nDCG@10 of both comparators,
with slightly lower recall. This audit measures fusion quality; it does not
measure candidate provider latency or prove provider-profile stability throughout
capture. The [frozen-run details](#frozen-producer-measurements) retain the capture
checks, cleanup error and excluded incomplete probe.

### Costs, tradeoffs and publication scope

The initial SciFact backfill of 5,183 complete documents took **33.68 seconds**;
derivative tables and indexes occupied **104,652,800 bytes**. Final reruns only
checked an already indexed corpus, so their migration timing is not indexing time.

On the 40 answerable documentation questions, passage evidence coverage changed
from **0.7000 to 0.6875**, while complete evidence stayed **0.6750**. Mean
wrong-product candidates increased from **0.6 to 20.575** within the returned
limit. Broader matching can recover relevant documents while also returning weak
candidates, including for unanswerable questions. Read the cited evidence and
use explicit syntax or structured filters for exact version selection.

This public report contains aggregate measurements, experiment settings and
public software/data provenance. Private deployment names and URLs, IP addresses,
account/space/source identifiers, credentials, document titles/bodies, private
questions/labels, raw rankings and operational paths are excluded. Raw evidence
is retained privately; the documentation corpus cannot be independently reproduced
from these aggregates. Public-corpus evaluations can be repeated with the
[BEIR runner](../benchmarks/retrieval/README.md), an authorized disposable instance
and the stated settings, but identical timing is not guaranteed.

See [release and acceptance evidence](../PLAN.md#document-bm25--released-core-consumer-adoption)
for the full PostgreSQL, packaging, HTTP/MCP, browser and native checks. Publication
of these measurements does not change or authorize a production deployment.

## Retrieval behavior

Ordinary source/Wiki queries use OR eligibility with English and Italian stem
variants and literal terms. `Bcl2`/`BCL-2` and `Tetraspanin-3`/`Tetraspanin 3`
share ordered alphanumeric variants; different numbers remain distinct. Repeated
query terms and stem aliases contribute once. Stop-only queries return no hits.
The 512-character input bound remains; no query is silently truncated. Numbers,
uppercase identifiers and weak matches in prose are relevance signals. Exact
selection uses quoted phrases, explicit operators or existing structured filters.
Explicit syntax retains PostgreSQL's existing strict interpretation.

BM25 (`k1=1.2`, `b=0.75`) scores complete current source documents and Wiki
revisions. Space, category, archive and annotation predicates restrict both
candidates and corpus statistics before ranking. The top 64 documents supply
existing source chunks, selected by query-term contribution with deterministic
ID ties. Citation bytes, hashes and offsets are unchanged. Source-only pagination
uses the same document ordering and retains its citation-list response. Multipart
sources retain their existing identities. Hybrid uses document-level RRF with
constant 60; semantic-only retrieval keeps its existing ranking.

Schema0036 stores document lengths and term frequencies with no additional body
copies. A numbered PostgreSQL normalizer is shared by writes, queries and migration
backfill. Derivatives follow complete-source publication and Wiki/title edits in
one transaction. Foreign-key cascades retire old derivatives. Migration preserves
all original document/chunk/revision identities and backfills retained bodies in
bounded statements within its existing atomic migration transaction.

Optional `lexical_strategy=websearch|relaxed|bm25` and
`lexical_ranker_version` describe actual lexical behavior independently of provider
modes. `bm25` remains text retrieval, without synonym expansion, translation or
answer generation. A relevant document may contradict the query. Read its exact
original evidence; relevance does not establish truth or a supported version.

Acceptance requires SciFact nDCG@10 ≥0.60, Recall@10 ≥0.65, empty results ≤10%,
and text P95 ≤1.5× a contemporaneous matched baseline. Previously inspected
SciFact queries are development evidence. Freeze the candidate before untouched
NFCorpus evaluation and require no aggregate nDCG/Recall regression. Hybrid must
remain within 0.01 nDCG@10 of both its baseline and semantic-only comparator.
Retain failing runs and revise candidates without changing these thresholds.
Record returned-candidate recall, oracle nDCG ceiling, distinct documents,
indexing time, index bytes and latency alongside corpus/provider provenance.
Private selectors, labels, raw rankings and operational evidence stay outside Git.

Use the [current-corpus runner](../samples/ingestion/examples/website/BENCHMARK.md)
for the existing documentation corpus and private labels, plus the real HTTP,
standalone wheel/archive and browser regressions. See [development](development.md).

## Frozen producer measurements

Candidate `4595054b35c20be276d4df7c1a0360b5ac340ab5` freezes Core package tree
`9f1009b6f50a52bf1ec8c10515f5d587a24008f5`. The M4 successor retains the same ranker and normalizer, with a new
Core version and migration identity; the package tree now includes M4.
Provider-free local PostgreSQL measurements use complete official corpora,
`kind=source`, limit 50 and reranking off, with identical query/corpus settings
for the contemporaneous baseline and candidate. Citation hashes and corpus
bodies are checked. These timings cover Core calls on the same host; they are
not public HTTP or deployed acceptance.

| Dataset and method | nDCG@10 | Recall@10 | Empty queries | P95 ms |
| --- | ---: | ---: | ---: | ---: |
| SciFact baseline | 0.3098 | 0.3372 | 156/300 | 168.8 |
| SciFact document BM25 | 0.6782 | 0.8073 | 6/300 | 175.6 |
| NFCorpus baseline | 0.2365 | 0.1024 | 82/323 | 142.6 |
| NFCorpus document BM25 | 0.3206 | 0.1538 | 18/323 | 133.6 |

SciFact was already development evidence. NFCorpus's 3,633 documents and 323
queries were first evaluated after the candidate was frozen; those questions
are now exposed. Fresh local citation IDs account for the small baseline
SciFact nDCG difference from the historical public run. SciFact returned-document
recall is 0.8802, oracle nDCG@10 is 0.8819, and mean distinct returned documents
is 48.68. Backfilling 5,183 complete documents takes 33.68s; derivative tables and
indexes occupy104,652,800 bytes.

Separate diagnostic ablations retain the explicit-syntax branch. Broader literal
chunk eligibility with summed term frequencies scores 0.4172 nDCG@10 /0.5694
Recall@10; adding normalization gives 0.4388/0.5786; chunk BM25 gives 0.6795/0.8043;
the selected document BM25 gives 0.6782/0.8073. These diagnostic variants are not
new public search options.

A matched fusion audit captures 64 actual semantic candidates per SciFact query,
uses the same arrays for all comparators, and applies Core's RRF implementation.
Candidate document hybrid scores 0.7388 nDCG@10 /0.8536 Recall@10, against baseline
hybrid 0.7198/0.8592 and semantic-only 0.7133/0.8559. It passes the declared nDCG
guardrail, with slightly lower recall. Model and dimensions match the historical
run below. All 300 queries and both source/version/body checks completed before
a client cleanup error; a separate incomplete probe is excluded. Twelve raw
rankings differ from the historical archive while aggregate comparator metrics
match. This audit does not establish candidate provider latency or controlled
provider-profile stability throughout capture. Raw evidence and failed probes
remain private.

The existing documentation benchmark was also run on251 approved current
originals and50 unchanged frozen questions. Fourteen source bindings changed;
all frozen evidence passages remain present, and both rankers use the same
copied corpus and metadata. Across45 queries with positive labels, nDCG@10
moves from0.5250 to0.6631 and Recall@10 from0.6444 to0.8407; empty results
across all50 move from11 to0. For the40 answerable questions, evidence coverage
moves from0.7000 to0.6875 and complete evidence remains0.6750. P95 moves from
91.8ms to146.9ms. Broad matching returns more weak candidates, including for
unanswerable questions; relevance is not an answerability test. The initial
local setup stopped before scoring because managed sources remained staged;
all bodies were validated before Core's normal publication operation completed
in the disposable fixture. Indexing time is unreported for that resumed run.
The later M4 successor was validated independently, as recorded below.

Current-base candidate `fbae9a2` reproduces the quality scores but fails the
SciFact latency gate: P95 286.0ms against149.4ms, exceeding1.5×. Its raw run
remains frozen. The next candidate batches citation loading and generation
checks; SQL count and exact citation regressions accompany that optimization.
The accepted successor passes new matched measurements without changing thresholds.

The accepted producer `bb88250` preserves all document rankings and citation
payloads while batching citation reads and final generation checks. Its exact
current-base comparison freezes lexical, retrieval and citation modules from
`b8ec5bf`; earlier batch timings with a shared citation helper remain diagnostic.

| Final matched dataset | Baseline P95 ms | BM25 P95 ms | BM25 nDCG@10 | BM25 Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| SciFact | 149.0 | 91.6 | 0.6782 | 0.8073 |
| NFCorpus | 128.7 | 56.8 | 0.3206 | 0.1538 |
| Documentation | 148.0 | 115.9 | 0.6631 | 0.8407 |

The final migration check is idempotent, not a new indexing-time measurement.
Documentation's mean wrong-product candidate count rises from 0.6 to 20.575;
exact-version wrong hits remain zero. This tradeoff accompanies the unchanged
evidence-coverage figures above. Current-source producer full/native acceptance
and immutable publication pass; released consumer PR100 also passes full/native
and image acceptance. Main full/native gates, canonical publication, independent
artifact audit and registry identity checks also pass. See
[acceptance evidence](../PLAN.md#document-bm25--released-core-consumer-adoption).
No production deployment is authorized by these measurements.

## Standard BEIR datasets

The local [BEIR benchmark](../benchmarks/retrieval/README.md) evaluates document
rankings against standard graded qrels through public authenticated C0 APIs.
Install its separate development environment, configure a dedicated protected
space and API key, run `benchmark ingest` once, then repeat `benchmark evaluate`
while testing retrieval changes. Corpus drift, incomplete vector coverage and
lexical fallbacks cannot silently count as successful semantic/hybrid results.
This does not replace the current-corpus documentation or agentic benchmarks.

## Measured SciFact results

A complete run on 6 November 2026 (UTC) measured real text, semantic and hybrid
retrieval through the authenticated public MCP API. All **300 eligible test
queries per mode** completed: **900 searches, zero errors, zero fallbacks and
zero effective-mode mismatches**. Both complete corpus checks passed, and the
embedding profile and coverage stayed unchanged. The comparison is valid.

| Mode | nDCG@10 | Recall@10 | MRR@10 | P50 ms | P95 ms | Errors | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Text | 0.3101 | 0.3372 | 0.3037 | 375.5 | 667.9 | 0 | 0 |
| Semantic | 0.7133 | 0.8559 | 0.6747 | 840.6 | 1199.9 | 0 | 0 |
| Hybrid | 0.7198 | 0.8592 | 0.6814 | 817.5 | 1151.7 | 0 | 0 |

Additional quality metrics use the same 300-query denominator:

| Mode | Recall@5 | Precision@10 | MAP@10 | Hit@1 | Hit@5 | Hit@10 | Duplicate chunk rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Text | 0.3356 | 0.0363 | 0.2991 | 0.2767 | 0.3433 | 0.3433 | 0.0505 |
| Semantic | 0.7723 | 0.0973 | 0.6638 | 0.5967 | 0.7867 | 0.8633 | 0.2388 |
| Hybrid | 0.7818 | 0.0977 | 0.6709 | 0.6000 | 0.7967 | 0.8667 | 0.2327 |

### Data and configuration

- **Dataset:** BEIR SciFact, test split; all 5,183 documents, 9,130 verified source
  chunks and 300 queries with test relevance judgments, from 1,109 query records.
  No document or eligible-query sampling was applied. Dataset fingerprint:
  `fcf803d2c4101b2faa5d88f1152b6b1815d2d46d8cb9c92e7670b616dcb0894c`.
- **Server:** app 0.60.0 at `a8bb2e8eb15906440835ebc94b1b300d083a0f6a`, released
  Core 0.39.0 at `b05ebe46e1857d7889b30e798005f7c2957a3a76`, schema 0033.
  Embedding model: `text-embedding-3-small`, 1,536 dimensions. All 9,130 source
  chunks had current embeddings before and after evaluation; actual semantic and
  hybrid searches established provider availability.
- **Search:** `kind=source`, `graph_depth=0`, limit 50 chunks, reranking off,
  one request per query per mode, sequential calls. An existing Wiki report was
  explicitly excluded with a revision/hash pin; only source-specific coverage
  counted toward readiness. No Wiki content contributed to the rankings.
- **Client:** Python 3.12.13, benchmark 0.1.0, ingestion 0.3.1, MCP 2.3.0 and
  httpx2 2.13.1. The benchmark/shared-client source came from the Core source
  above. Use the [runner instructions](../benchmarks/retrieval/README.md) with
  the same dataset and settings for a new evaluation in an authorized space.

The evaluator verified every document's current generation, body, chunk hashes
and offsets before and after searching, checked corpus metadata between modes,
and matched returned citations to verified chunks. Source-specific indexed
counts equaled the verified chunk count throughout. Changes restored entirely
between verification calls cannot be ruled out through the public APIs.

### Interpretation and limits

Semantic and hybrid retrieval score higher than text retrieval in this run.
Hybrid's nDCG@10 is slightly higher than semantic's; a single pass does not
establish statistical significance or an improvement on other corpora. Text has
the lowest measured median latency. P50/P95 are end-to-end client observations,
including network and provider time, with nearest-rank percentiles; cold caches
and controlled deployment load were not established.

Quality is a macro average over all eligible queries; empty rankings score zero.
The [metric definitions](../benchmarks/retrieval/README.md#valid-comparisons-and-reports)
follow BEIR/trec_eval conventions. Multiple returned chunks from one document count
once at its first rank; a 50-chunk limit can yield fewer than ten documents.
This measures retrieval rather than generated-answer quality, and relevance
labels can be incomplete.

This section publishes aggregate measurements, public software/data identities
and experiment settings. Raw reports, per-query rankings and operational receipts
remain private because they contain deployment and account selectors.

## Historical provider fixture

The measurements below are retained historical evidence, not a comparison with
the new lexical strategy or proof of real provider quality.

### Retrieval fixture benchmark

Measured with actual PostgreSQL/pgvector and deterministic protocol mocks. Eight immutable Wiki revisions contain two relevant paraphrases and two keyword distractors for each of two queries. Each query returns at most two results. No generated answers, real provider calls or calibrated model probabilities are tested.

| Strategy | Recall@2 | Precision@2 | Citation coverage | Mean local ms | Candidates/query | Scored/query | Query embedding bytes | Scorer request bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| text | 0.00 | 0.00 | 1.00 | 3.22 | 2 | 0 | 0 | 0 |
| semantic | 1.00 | 1.00 | 1.00 | 11.88 | 8 | 0 | 156 | 0 |
| hybrid | 0.00 | 0.00 | 1.00 | 10.88 | 8 | 0 | 156 | 0 |
| hybrid_helpful | 1.00 | 1.00 | 1.00 | 11.88 | 8 | 8 | 156 | 7550 |
| hybrid_unhelpful | 0.00 | 0.00 | 1.00 | 11.05 | 8 | 8 | 156 | 7550 |

Byte totals cover both queries and count serialized mock request payloads; they exclude HTTP/TLS overhead, background indexing and paid provider pricing. Latency is one local observation per query/strategy and includes mock adapters/database work, with no real network inference. Citation coverage means each hit carries an immutable Wiki revision reference; it does not establish claim truth or answer quality.

Semantic mock vectors find the paraphrases. RRF gives repeated keyword distractors priority in this adversarial corpus. A deliberately helpful scorer recovers both relevant hits; a deliberately unhelpful scorer leaves the distractors first. This demonstrates both useful composition and degradation: optional scoring needs corpus/model evaluation and threshold calibration. Keep text mode and scoring-off overrides available. No real OpenAI scoring improvement is claimed by these mocks.

Reproduce with an isolated PostgreSQL/pgvector database and CZERO_BENCHMARK_OUTPUT pointing to a temporary JSON file, running tests/integration/test_retrieval_benchmark.py. CI executes the same quality/citation assertions.
