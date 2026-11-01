# Controlled agentic retrieval experiments

These are external development workflows, never a production maintenance service.
Use the three repository skills in `.agents/skills`: generate retrieval questions,
maintain semantic layer, and benchmark agentic retrieval. They compose through
`scripts/evaluate-agentic-retrieval.py`. Existing `evaluate-tools.py` supplies the
isolated Codex driver, real authenticated MCP fixture and parent-side traces;
`c0_benchmark` supplies document metrics. No Core or runtime change is required.

## Protocol version 1 (freeze before model calls)

A corpus contains current original bodies, canonical URLs, logical IDs, generation
IDs, SHA-256 hashes and source chunks. Freeze a private manifest. Question generation
reads those bodies, without search results. Labels have required evidence units;
each unit lists acceptable passages and documents, and alternative complete sets
are supported. Exact quotes, generations and hashes must validate before freezing.
Agent labels remain provisional analyst labels; deterministic quotation checks do
not establish entailment. Audit representative multi-hop, version, ambiguous,
unanswerable and cross-language cases separately.

Partition by question type/answerability/language before tuning. Development may
inform improvements; validation and sealed test are single-use, including failures.
Old or exposed benchmarks belong to development. Keep builder and grader artifacts
outside model workspaces. A retrieval episode sees one question and selected space,
fixed read guidance and actual discovered C0 read tools, never labels or partitions.
Each episode uses a fresh process/workspace. The eager adapter is experimental;
it does not establish native connector discovery or ChatGPT compatibility.

Matched arms use one disposable database snapshot: sources retain identical IDs,
generations, metadata and hashes. Run A before adding derived records, then B after
adding them. Both arms have the same read-only scopes, catalog and instructions.
Source manifests must match before/after every episode. No global providers change.
A failed arm stays in the results; do not selectively retry a poor outcome.

Default budgets: 12 calls, 180 seconds/episode, 512 KiB total catalog/prompt/result context,
200,000 observed cumulative tokens/episode; 80 model sessions, 4,000,000 observed tokens and
7,200 seconds per experiment; at most three development rounds and two repetitions. At most13 model requests
per12-call episode gives an explicit1,040-request ceiling across80 sessions;
observed usage-event counts are retained, without claiming hidden provider calls.
Token accounting is observed at app-server usage events, with possible one-event
overshoot; missing usage prevents efficiency acceptance. Context is bounded before
forwarding a response. Wall deadlines and process termination remain hard limits.
Do not claim a provider-side token cap or immutable backend snapshot.

Default acceptance (save overrides and rationale before the first candidate):
complete-evidence success >=0.80 and >=0.10 absolute improvement on answerable
questions; when A >=0.90, B may lose at most0.05 while median calls improve20%.
All submitted citations must resolve to actually observed current originals;
no unauthorized/write attempts or source drift; zero known product/version errors;
ambiguous clarification and unanswerable abstention each >=0.80. Mean calls <=12,
P95 <=180s, mean observed tokens <=200,000. These are pilot thresholds, not production
SLAs. Small provisional samples cannot establish population confidence.

Stop on safety/citation regression, drift, exhausted budget, unavailable model,
no meaningful development improvement, or acceptance. Preserve every attempted
candidate. Select using development only, run validation once, then sealed test
once only if validation passes. Never tune after viewing validation/test failures.
A resumed session skips completed episodes and retains failures; an uncertain
in-flight episode is blocked for reconciliation, not automatically replayed.

## Semantic profile

The semantic layer is authored C0 knowledge supported by original evidence:
entities/aliases, typed objects/relations, claims, applicability/verification and
sourced Wiki navigation. It is not embedding search or a separate database.
The minimal automated profile here manages **sourced Wiki navigation records**.
Each record has a namespaced stable slug, extractive source passages, a separately
labelled synthesis, original chunk references and an unverified annotation bound
to those references. Literal version tags remain literal; missing metadata remains
unknown. Original evidence is authoritative. Entity/claim/typed-record expansion
requires an explicitly approved profile using the existing APIs, not guessed types.

Initial construction receives only corpus and profile, never questions. Development
feedback may motivate generally useful navigation, but every passage must independently
match a current source. Do not index questions, IDs, gold keys or evaluation advice.
Plans reject unknown fields and benchmark-shaped data; compare proposed body/title
against private question text/IDs before applying. Inspect proposed changes before
`apply`. Model output never becomes verified knowledge automatically.

Managed state stores request intents before writes. Reuse exact replay keys after
uncertain writes; reconcile readback, never clear an intent to force a retry.
Updates require the saved current revision/body hash and namespace marker. Conflicts
stop without overwriting authored edits. Do not delete sources or unrelated records.
Verification checks source generation/hash and citation resolution. Superseded source
references make records stale; C0 annotations retain unavailable references without
old bodies. Access loss stops the workflow. A new current source needs a reviewed
new plan; never silently rebind an expired reference.

## Commands and private inputs

Run with the producer development Python environment from `docs/development.md`.
The CLI `--help` lists freeze, questions, freeze-labels, layer, maintain, validate, loop and status commands. Inputs
are private JSON, validated by the tooling; output directories must be new/private.
No tokens belong in command arguments or Git. Disposable runs use only an explicit
`CZERO_EVAL_DATABASE_URL` loopback administrator and existing local Codex sign-in.
The selected model must equal its reported identity; no automatic substitution.
Local model catalog availability alone is not inference access.

Metrics: complete evidence is all units of at least one labelled complete set present
in submitted, actually observed and current original passages. Passage coverage is
the largest covered fraction of those sets. Answerable questions alone form these
means and document recall denominators. Hit/Recall/MRR reuse the existing benchmark
formulas and deduplicate logical source parents. Citation validity divides valid
submitted citations by all submitted citations (null for no submissions). Search
rankings, evidence reads and graph traversals remain distinct raw traces. Search
hits alone do not establish clarification, abstention or answer correctness.
Disposition is graded separately. Free-text unsupported claims/entailment require
manual review; do not call an unchecked answer correct. Report product/version
unknowns separately, token/call/context waste and nearest-rank P50/P95 with N and
first/repeat distinction. Provider costs are unknown unless actually reported.

The installed driver supports explicit pinned CLI versions, observed model identities
and bounded real calls. See [the existing driver limitations](tool-evaluations.md)
and [official app-server guidance](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server).


```sh
# New private ingestion job uses existing approved credentials; never a mirror.
python scripts/evaluate-agentic-retrieval.py freeze --job /private/job --output /private/snapshot
python scripts/evaluate-agentic-retrieval.py questions --corpus /private/snapshot/corpus.json --output /private/questions-proposal
python scripts/evaluate-agentic-retrieval.py layer --corpus /private/snapshot/corpus.json --output /private/layer-proposal
python scripts/evaluate-agentic-retrieval.py maintain dry-run --job /private/job --corpus /private/snapshot/corpus.json --plan /private/plan.json --questions /private/questions.json --state /private/managed.json
# After reviewing the dry-run, use the same inputs with: maintain apply
# Read-only reconciliation: maintain status / maintain verify
CZERO_EVAL_DATABASE_URL="$CZERO_TEST_DATABASE_URL" python scripts/evaluate-agentic-retrieval.py loop --sources tests/evaluation/agentic_sources.json --output /private/synthetic-run
python scripts/evaluate-agentic-retrieval.py status /private/synthetic-run
```

`loop --sources` accepts explicitly selected JSON originals with key/title/url/body/
product/version/language. `--config` overrides the bounded defaults in the CLI;
`--help` never prints credentials. Full current bodies and canonical metadata are
read through supported APIs. This minimal profile blocks multipart selections;
use a bounded single-document pilot rather than silently flattening parent mappings.
The paired fixture clones only invocation-owned disposable databases before any
model episode. Its original source identities and generations are identical.
Raw authentication/state setup is reused from the existing evaluation fixture.

Checkpoints retain episode reservations, completed failures, plans and exact pending
write intents. Maintenance can resume exact uncertain writes using its saved state.
Paused paired experiments retain only their own random disposable databases in a
mode-0600 `database-binding.json`, including synthetic fixture identity. `loop
--resume` verifies their database ownership nonce, original IDs/hashes and exact
protocol/code before continuing. Completed/failed episodes are never silently
retried; an uncertain in-flight episode requires reconciliation. Validation and
sealed failures are terminal. `cleanup OUTPUT` removes only ownership-proven
retained databases; it cannot name another database. Terminal completed experiments
remove their disposable databases automatically.

The first `loop` invocation prepares questions/partitions and a source-only layer
proposal, then stops at `prepared_requires_audit`. Review a representative sample
against original bodies independently of rankings. Save private `label-audit.json`
with `proposal_hash` matching the digest of `proposal.json`,
`reviewed_questions_hash` matching the reviewed question list,
`approved_for_pilot: true`, and an
`audit` list describing selected question IDs, checks, uncertainties and analyst
provenance. This is an analyst attestation, not independent human adjudication.
Before any retrieval, corrections may be saved in `questions-reviewed.json`;
retain the original proposal and audit every correction against originals.
The final partition/label freeze is written only after this audit. Then resume the unchanged protocol with `loop --resume` and the same arguments.
Use `--prepare-only` to stop after preparation explicitly. Keep that audit, labels
and all model traces outside Git. No production application is implied.


To repeat an invalid runner experiment after a separately committed correction,
`loop --prepared /private/previous-run` reuses its frozen questions, partitions
and source-only initial plan. It permits only identity rebinding after exact URL,
normalized body/hash, metadata and chunk-layout checks. Audit the new bindings
before scoring. It never imports old calls or grades into measured episodes.
Previously evaluated validation/test sets are marked exposed and moved to development;
they cannot become a fresh sealed test. Preserve both failed and corrected runs,
label the driver/grader revisions and avoid comparing across an invalid measurement.


Independent semantic maintenance does not require benchmark data. Pass optional
`maintain --questions` only when evaluation material exists and needs a private
leakage check; the builder still receives originals alone. Standalone dataset
construction can use `freeze-labels --corpus ... --proposed ... --reviewed ...
--audit ... --plan ... --output ...` after source-based analyst review, without
starting a model or database. Its audit uses the same proposal/review hashes as
`loop`; failed proposals remain separate from final frozen labels.
