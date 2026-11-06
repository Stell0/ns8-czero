# Local C0 BEIR retrieval benchmark

This repository-only development tool measures document retrieval through an
already deployed C0 instance's authenticated public MCP API. It sends every
selected BEIR query to `knowledge_search`, with `kind=source`, `graph_depth=0`,
and explicit mode, rerank, space and limit parameters. It never implements a
search engine or changes server algorithms or provider configuration.

Ingestion and evaluation are separate. **Evaluation makes only read-only API
calls** and can use a separate Read-only key for the same account/space. Local
reports, downloaded datasets, locks and manifests are written by both commands.
Nothing here is installed by the NS8 module, app/Core distributions, plugin
packages or container COPY rules. No deployment is needed.

## Install and configure

From the repository root, with Python 3.12–3.14:

1. In C0, create an **empty dedicated protected space**, with Write access for
   your account. Use a different space for each dataset. Do not initialize managed
   project workflows, create a schedule or import into Shared.
2. On Account, create an API key with Read and Write scopes and **only that
   protected space**. Record the exact account ID, account nickname and space ID.
   The key cannot elevate the account's current permissions.
3. Install the two local packages into a dedicated environment:

   ```sh
   python3 -m venv .venv-benchmark
   . .venv-benchmark/bin/activate
   python -m pip install -e samples/ingestion -e benchmarks/retrieval
   benchmark --help
   ```

4. Configure the selectors and supply the key from your secret manager or shell:

   ```sh
   mkdir -p .local/benchmark
   cp benchmarks/retrieval/config.example.toml .local/benchmark/config.toml
   chmod 600 .local/benchmark/config.toml
   # Edit URL (/mcp), account ID/nickname and protected space ID in that file.
   read -r -s -p 'C0 API key: ' C0_API_KEY; echo
   export C0_API_KEY
   ```

   Run commands from the repository root, or pass `--config` explicitly. Paths in
   TOML are relative to its directory. No secret is accepted in the TOML file.
   `.local/benchmark/` is ignored by Git. Keep custom paths outside Git too.
5. Import once, then evaluate repeatedly:

   ```sh
   benchmark ingest
   benchmark evaluate
   benchmark evaluate --mode text
   benchmark evaluate --mode semantic --mode hybrid --repetitions 3
   benchmark evaluate --mode hybrid --rerank rerank
   ```

Defaults: SciFact, test split, text/semantic/hybrid, reranking off, 50 returned
chunks. CLI `--mode` is repeatable and replaces the configured modes. `--limit`
is the **C0 chunk limit**, between 10 and 50, not a query/corpus sampling option.
Repetitions (1–5) measure latency; only the first request scores quality. Rerank
values `rerank` and `filter` require support/configuration on the deployed instance.
An unsupported request stops the experiment and records an invalid run.

## Datasets and ingestion recovery

[SciFact, NFCorpus and FiQA](https://github.com/beir-cellar/beir#beers-available-datasets)
can download from BEIR's public dataset host, once per cache directory. Download
and extraction sizes, archive paths and link types are checked before atomic cache
publication. A failed download leaves no valid-looking cache; a malformed existing
cache fails explicitly. Dataset licenses and domains differ; review their terms.

```sh
# Configure the matching dedicated space in each private TOML file first.
benchmark ingest --dataset nfcorpus --config .local/benchmark/nfcorpus.toml
benchmark evaluate --dataset nfcorpus --config .local/benchmark/nfcorpus.toml
benchmark ingest --dataset fiqa --config .local/benchmark/fiqa.toml
benchmark evaluate --dataset fiqa --config .local/benchmark/fiqa.toml
benchmark ingest --dataset custom --dataset-path /path/to/beir
benchmark evaluate --dataset custom --dataset-path /path/to/beir --split test
```

Compatible directories contain unmodified `corpus.jsonl` (`_id`, `title`, `text`),
`queries.jsonl` (`_id`, `text`) and `qrels/<split>.tsv` with the standard
`query-id`, `corpus-id`, `score` header. IDs remain strings and grades remain
integers. All referenced query/document IDs must exist; duplicate IDs/judgments,
malformed records, negative grades and evaluated queries without positive judgments
are rejected. Only queries in the selected qrels are evaluated. A full SHA-256
fingerprint includes the complete original corpus, all queries, graded qrels and
split, independent of file order. Keep the same cache or copy alongside saved runs.

The searchable body is exactly `title + "\n\n" + text`, or `text` when title is
empty. The server source title is a stable bounded label; the full original title,
text and BEIR ID remain in the local dataset and the original title is searchable
in the body. Source metadata binds dataset, fingerprint, BEIR ID and body hash.

One BEIR document maps to one C0 source. This runner deliberately uses the existing
idempotent text-ingestion API, **1–131072 UTF-8 bytes per combined document**. The
whole corpus is preflighted before writes. Larger items fail with their ID; nothing
is truncated, omitted or split. Custom datasets with larger items require a future
reviewed upload adapter, not a smaller corpus passed off as standard BEIR. Queries
above the deployed API's 512-character bound also fail before searching.

Manifests bind URL, account, exact protected space, dataset and split. They save
source/version/document/chunk identities, revisions, hashes and offsets. Ingestion
first submits all missing documents to C0’s existing background extraction queue,
without waiting for each document to finish. It then verifies every original body
and chunk before marking the corpus complete. Submission requests remain sequential;
there is no new server bulk endpoint or concurrent upload pool.

Writes use shared deterministic idempotency keys; a pending intent is fsynced
atomically before I/O. Each successful reply saves an acknowledged submission
receipt before the next request. `submitted` counts queued or not-yet-verified
items; `documents` contains only fully verified items. Neither queued nor
acknowledged means extracted or searchable. After interruption, rerun **the
identical** `benchmark ingest` command:
completed items are verified with zero writes; acknowledged submissions retain
their exact source/version/hash identities and are never resubmitted. The one
uncertain pending intent is reconciled against remote metadata, then its whole
body is verified after processing. If absent after a successful inventory,
only its identical idempotent submission can be replayed. There is no blind retry
loop. Unrelated sources or Wiki pages, missing completed items, changed metadata,
versions or bodies stop ingestion without overwriting or deleting anything.
Existing manifests from the earlier one-document-at-a-time runner can resume
with this updated runner. Keep using the updated runner once submission receipts
exist; the earlier version does not understand that queue.
The process lock serializes use of the same local state directory. Keep that
manifest: this tool refuses to adopt an existing remote corpus without receipts.

Calls are sequential (concurrency one), the shared HTTP client has a 60-second
request timeout, and extraction/index polling has explicit bounded attempts and
intervals. Progress distinguishes submitted and verified documents. The unchanged
`benchmark ingest` command submits the full corpus, waits for background processing
and verifies it; `benchmark evaluate` still refuses an incomplete corpus. A large
queue may outlast a bounded wait: rerun the identical ingest command to continue
verification without submitting acknowledged items again. No source
retry/reindex/delete/update operation is called. Failed extraction requires separate
operator diagnosis. The ingestion manifest retains cumulative ingestion/readback
and subsequent indexing-wait durations across invocations.

## Valid comparisons and reports

Source readiness and vector readiness are separate. C0 currently exposes an
embedding profile/model/generation and indexed count, rather than per-chunk
embedding receipts. The runner infers full coverage only when that count equals
all verified current chunks in the dedicated source-only space. Incomplete
coverage invalidates semantic/hybrid comparisons; ingestion reports it and can be
rerun to wait longer without rewriting documents. Text can be measured separately.
Provider connectivity is established only by actual searches, not the count.

Evaluation verifies the complete corpus before and after searching and checks it
between modes. It detects missing/additional/changed/unready sources, revisions,
versions, bodies and chunk identities. Every returned citation must match the
verified source/version/document/chunk/hash/offset identity. Repeated chunks from
a document retain their original order in debug output and count once at the
document level, at the earliest occurrence. Fifty chunks can yield fewer than ten
documents; the benchmark never invents missing results.

Any fallback or effective method mismatch invalidates **the whole requested mode**;
no partial macro score is presented as standard semantic/hybrid/reranked quality.
Errors stop the experiment, retain completed diagnostic rows and mark the run
invalid. Exit codes: 0 for success, 2 for a completed run containing unavailable or
fallback modes, 1 for a configuration/API/corpus error. Successful text scores can
still appear beside explicitly unavailable semantic modes. A corpus/index drift
invalidates all modes. Changes restored entirely between verification calls cannot
be excluded through today's public APIs.

Every evaluation attempt after loading the manifest creates a fresh directory:

```text
.local/benchmark/results/<dataset>/<UTC timestamp>-<random suffix>/
  summary.json    # configuration, fingerprints, capabilities/version, index/model, metrics
  queries.jsonl   # text, graded qrels, effective method, lexical strategy, errors/fallbacks,
                 # candidates, provider usage, per-query quality and all latency repetitions
  rankings.jsonl  # document ranks, original chunk ranks, complete scored raw hits/citations
  report.md      # comparison table, availability, validation and worst queries
```

The main comparison table also prints in the terminal. The CLI additionally reads
public health version metadata when available, and records local Python/client
versions and the benchmark source hash. Reports contain private
instance/account selectors and query text, but never API keys or request headers.
Store/share them accordingly. Report content is deterministically derived from the
saved rows and summary; timestamps, measured latency and run IDs naturally vary.
To compare a retrieval change, use identical dataset/corpus/config fingerprints,
profile/model, reranking and limits, then compare the tables and per-query rows:

```sh
ls .local/benchmark/results/scifact/
diff -u /path/to/previous/report.md /path/to/new/report.md
python -m json.tool /path/to/previous/summary.json
```

Quality is a macro average over all qrels queries, including empty rankings as
zero. It follows [BEIR's trec_eval methodology](https://github.com/beir-cellar/beir/blob/main/beir/retrieval/evaluation.py):
linear graded nDCG@10, binary positive relevance for Recall@5/10, MRR@10,
Precision@10, Hit@1/5/10 and MAP@10 (denominator: all relevant documents).
Precision always divides by 10. Query/document IDs are independent namespaces;
identical IDs are not filtered. C0 order determines ranks, regardless of score
scale. Duplicate chunk rate is `(chunks - unique documents) / chunks`, zero for no
results. Latency P50/P95 uses nearest-rank percentiles of all attempted requests;
first/repeated requests remain identifiable, and repetitions do not inflate
quality denominators. No cold-cache claim is made.

BEIR measures retrieval quality, **not answer generation, extraction fidelity or
overall RAG assistant quality**. Labels may be incomplete. This tool exercises
C0's extraction pipeline and bounded chunk results, not an unbounded full-document
retriever; corpus completeness and vector readiness are prerequisites to useful
comparisons. The existing documentation/agentic benchmarks remain independent.

## Offline tests and reference verification

No C0 instance, provider or BEIR download is used by the synthetic tests:

```sh
python -m pip install -e 'benchmarks/retrieval[test]'
python -m pytest -q tests/unit/ingestion/test_beir.py tests/unit/ingestion/test_beir_packaging.py
python -m pytest -q benchmarks/retrieval/tests
```

The last command compares metric calculations against BEIR's actual `pytrec_eval`
reference dependency, pinned in this local tool's test extra. The normal repository
suite uses frozen reference values without adding numerical/BEIR dependencies to
C0 or its CI environment. Live ingestion/evaluation is explicitly opt-in through
the CLI and is never part of automated tests. No live benchmark has been run as
part of implementing this tool.
