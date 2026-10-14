# Retrieval fixture benchmark

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
