# Measure retrieval on a current documentation corpus

This external runner uses the job's dedicated OAuth connection and actual C0
APIs. It never reads C0's database or changes retrieval providers. Keep bindings,
questions, analyst labels and results in a private job. Pause that job's timer
while measuring; restore it even when a comparison fails. Other projects and
the C0 worker keep running.

Install the ingestion distribution and use its Python environment:

```sh
python -m c0_benchmark snapshot --job /private/documentation --output /private/frozen
python -m c0_benchmark run --job /private/documentation \
  --corpus /private/frozen/corpus.json --questions /private/questions.json \
  --config /private/benchmark.json --output /private/run-001
```

Output directories must be new. The runner locks the documentation job, verifies
whole current bodies and hashes, and records current IDs, generations, canonical
URLs, product/version/language metadata and corpus hash. Each mode checks the
manifest before and after retrieval. Changes invalidate the comparison, even if
an identical body later returns with a different generation. Saved manifests and
rankings are evidence; this does not restore document version history.

The entire selected space must contain the intended corpus. Publish operational
recipes after the baseline, or use a separate corpus space. Wiki hits are excluded.
Unknown source parents, staging, missing URLs, duplicate canonical URLs and stale
citations block measurement. Resolve authorization errors; they never become
empty result sets or a reason to switch space.

`benchmark.json` is a private configuration, for example:

```json
{
  "limit": 50,
  "repetitions": 2,
  "max_queries": 400,
  "modes": [
    {"mode": "text", "rerank": "off"},
    {"mode": "semantic", "rerank": "off"},
    {"mode": "hybrid", "rerank": "off"}
  ]
}
```

`limit` is the identical chunk budget for every requested mode (10–50).
Unconfigured embeddings produce an unavailable result without provider calls.
Only request reranking after independently checking the installed provider and
approval. Save runtime/source, embedding model/dimensions and reranker settings
beside the configuration. Provider errors and actual text fallback remain labelled
fallback; they never contribute to successful semantic/reranked quality means.
No model/provider costs are inferred from request counts. Raw API replies include
available provider usage, candidate/scored counts and fallback reasons.

When supported, `lexical_strategy` records strict web search or bounded relaxed
lexical matching separately from `retrieval_method`. Relaxed lexical matching is
still text retrieval. Older servers can omit this optional field; record that as
unreported, not semantic. Freeze product/version/language metadata along with the
bodies because declared provenance can affect lexical eligibility. See the
[query behavior](../../../../docs/retrieval-benchmark.md).

Snapshots also bind each physical part's source revision and the exact declared
product/version fields used by lexical matching. A metadata-only edit can
invalidate a comparison even when its body hash is unchanged. After a snapshot
format change, create a new snapshot and preserve prior manifests/results; do
not edit an old manifest to make its hash pass.

Each entry in `questions.json` has this structure (replace all fabricated values):

```json
[
  {
    "id": "q01",
    "text": "How do I configure the example service?",
    "language": "en",
    "products": ["Example"],
    "versions": ["8"],
    "answerability": "answerable",
    "split": "held_out",
    "confidence": "provisional analyst label, medium",
    "label_provenance": "Original manual and verified imported body read before retrieval",
    "relevant": [
      {
        "url": "https://docs.example.org/manual/configuration",
        "content_hash": "replace-with-current-sha256",
        "passages": [["exact expected evidence", "acceptable alternative"]]
      }
    ]
  }
]
```

Each inner passage list represents acceptable alternatives for one required
evidence unit. Several lists/documents represent evidence needed together.
Every alternative must occur in its labelled current body. Choose labels by
reading originals independently of rankings. Record provisional provenance,
confidence, product/version applicability and clarification alternatives. Reserve
held-out questions before tuning; do not change labels to reward returned hits.
Use `ambiguous` and `unanswerable` separately, with no relevant documents for the
latter. Returned results cannot demonstrate abstention or clarification behavior.

## Metric definitions

Chunk rankings are saved unchanged; document rankings retain the first occurrence
of each logical parent. Thus several chunks from one manual page count once.
For answerable questions, Hit@1/5/10 means at least one labelled relevant document
in the first k distinct parents; Recall@5/10 is the fraction of all labelled
relevant URLs there; MRR@10 is reciprocal rank of the first relevant parent (zero
when absent). Macro means weight questions equally. The actual returned chunk
budget can yield fewer than ten distinct parents; do not backfill with invented
results. Unanswerable questions have no recall/MRR denominator. Ambiguous cases
are reported separately, without asserting an answering policy.

Evidence coverage is the fraction of labelled passage units present verbatim in
returned chunks; complete evidence means every required unit is covered. This
measures retrieval, not entailment or generated answer quality. Duplicate rate is
`(chunks - distinct parents) / chunks`, zero for no hits. Product errors count
returned parents outside the question's explicit product set; version errors count
known versions outside its version set. Unknown version metadata is separate.

Quality uses the first repetition only; all timings are retained. Latency is the
client-observed retrieval call (including transport/refresh), excluding corpus
verification. P50/P95 use the nearest-rank empirical quantile and include sample
sizes. First and repeat requests are distinguished; a cold backend cache is not
established. Report development and held-out subsets separately and treat a small,
agent-labelled set as exploratory. Preserve individual failures for analysis.

## Comparator handoff

Do not call ticket webhooks, create support notes or reuse a production index for
reindexing. A matched-corpus adapter must use an approved read-only interface or
disposable index and return the following contract:

```json
{
  "corpus_hash": "exact-c0-manifest-hash",
  "question_id": "q01",
  "retrieval_method": "actual-comparator-method",
  "fallback_reason": null,
  "hits": [
    {"url": "https://docs.example.org/manual/configuration",
     "content_hash": "exact-normalized-document-hash",
     "chunk_id": "comparator-passage-identity", "body": "retrieved passage"}
  ]
}
```

`c0_benchmark.comparator_result` validates corpus/question bindings and every hit's
canonical URL/content hash, and normalizes rankings for the same `metrics`
function. Supply per-call latency, model/chunking/filter/context budgets and
provider usage separately. First reconcile the comparator's complete corpus
manifest, including documents never retrieved. The same rankings do not establish
corpus equality. A broader operational support-bot evaluation is a separate
experiment with its own corpus coverage. Without approved access, report **not
run**, preserve this handoff and finish the C0 baseline.
