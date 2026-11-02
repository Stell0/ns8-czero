---
name: c0-generate-retrieval-questions
description: Generate and validate provisional retrieval questions from explicitly selected current C0 source bodies, then freeze private evidence labels and development, validation and sealed partitions. Use for evaluation dataset construction, not answering a user question.
---

Read [the evaluation protocol](../../../docs/agentic-retrieval.md). Accept an explicit
current corpus manifest, bounded generation settings and new private output path.
Use `scripts/evaluate-agentic-retrieval.py questions --corpus ... --config ...
--output ...`. Generation does not require a retrieval fixture, semantic layer or prior audit.
Use bounded source packets and explicit question_counts where needed; packet
absence alone cannot establish full-corpus unanswerability. It uses the existing isolated model driver; preserve requested and
reported model identities and every failed attempt. Use approved Luna access where
available; absence is a blocker, never permission to substitute another model.

Generate labels from original bodies independently of search results. Cover exact
terms/paraphrases, configuration/troubleshooting, multiple documents and relations,
product/version conflicts, ambiguous and unanswerable cases. Report Italian against
English separately. The helper validates literal passages, current hashes and
source generations. Evidence alternatives are grouped into complete sets; one
search hit cannot stand in for all required evidence.

Audit representative labels for entailment, applicability and missing evidence.
Record analyst provenance/confidence/uncertainty: model labels are provisional, not
independent human adjudication. Correct invalid labels before freezing, retaining
failed generation artifacts. Partition before tuning, stratifying where practical.
Old or exposed held-out sets are development evidence. Never rewrite frozen labels
to reward a retriever. Keep all questions, gold labels and partitions outside every
retrieval episode workspace. Provide only its current question to the agent.
