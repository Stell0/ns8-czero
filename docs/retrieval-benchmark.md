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

Semantic mock vectors find the paraphrases. RRF gives repeated keyword distractors priority in this adversarial corpus. A deliberately helpful scorer recovers both relevant hits; a deliberately unhelpful scorer leaves the distractors first. This demonstrates both useful composition and degradation: optional scoring needs corpus/model evaluation and threshold calibration. Keep text mode and scoring-off overrides available. No real Jev/Kev improvement is claimed.

Reproduce with an isolated PostgreSQL/pgvector database and CZERO_BENCHMARK_OUTPUT pointing to a temporary JSON file, running tests/integration/test_retrieval_benchmark.py. CI executes the same quality/citation assertions.
