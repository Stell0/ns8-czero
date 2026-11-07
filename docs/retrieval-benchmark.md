# Provider-free question matching

Core 0.36.1 is independently published from merged source `8dbb746` after exact
full/native acceptance and supplied wheel/archive tests. The app 0.57 consumer
candidate selects its immutable tag and lock; consumer image/native acceptance
and guarded deployment remain separate gates.

Ordinary, filtered and source evidence search first run the existing PostgreSQL
`simple` web-search query. Existing matches retain their ranking. If the eligible
selection has no strict matches, an unquoted plain query with at least four
lexemes can use bounded lexical recovery:

- Words on either standard PostgreSQL English/Italian stop list are omitted from
  coverage. Remaining lexemes are neither stemmed nor translated.
- Two to 32 distinct remaining terms are required; longer selections stay strict
  without truncation. A candidate must match at least two and at least half.
- Numeric terms, uppercase identifiers and punctuated technical names remain
  mandatory. Current source provenance's declared product/version can supply
  context, while candidate discovery still requires a real chunk match with a
  GIN-indexable predicate. Annotation filters and space/current-generation predicates stay
  mandatory.
- Quoted phrases, `OR` and exclusions retain their original interpretation.
  Forms containing `&`, `|`, `!`, uppercase `AND` or `NOT` also remain strict;
  no SQL-style operator parser is added. Inline diagnostic punctuation such as
  `Check(flag)` does not itself mean Boolean grouping.

`knowledge_search` and its structured counterpart expose optional
`lexical_strategy=websearch|relaxed`. Null means unreported or unused. Relaxation
is still `retrieval_method=text`; semantic/hybrid provider fallbacks keep their
separate reasons. Source-only search keeps its existing citation-list shape and
chooses its strategy independently of pagination offset.

This corrects zero-result lexical eligibility, not synonymy, translation or
answer generation. Read the actual evidence. Missing metadata, acronyms absent
from a body, separated chunk terms and incomplete relevance labels can still
limit retrieval. Returned results do not establish abstention or clarification.

Use the [current-corpus runner](../samples/ingestion/examples/website/BENCHMARK.md)
with private labels, matched budgets and corpus guards. Preserve original
baselines, reserve fresh held-out questions before implementation, predeclare
quality/latency targets and record actual strategy/provider use. The real-HTTP
regressions, independent wheel/archive probes and HTTPS worker/Chromium tests
exercise the same Core behavior. See [development](development.md) for commands.

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
